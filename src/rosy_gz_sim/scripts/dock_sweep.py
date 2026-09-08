#!/usr/bin/env python3
"""Gazebo sweep for the dock detector rig.

Moves the dock over a ground-truth grid, samples one scan per pose, runs the
ROS-free fit, and appends a row per sample. The robot never moves: teleporting
it fights the controller, while relocating a static model is exact and free.

Ground truth is exact here, which is the whole reason this lane can afford
hundreds of samples where the bench affords tens.

**Every row is a scan that provably postdates its own pose change.** The
earlier version cleared `self._scan` and took the first arrival, which cleared
the Python attribute and not the middleware queue: with `KEEP_LAST` depth 1 and
no spinning between grid iterations, a sample generated before `set_dock_pose`
returned was already queued and the first `spin_once` handed it over. Sample N
was systematically a scan of pose N-1. The dock-absent phase is where that
bites: one stale pre-park frame still showing the dock produces a fit on a row
labelled `dock_present=False`, one false positive, and the geometry candidate
fails the design's strongest criterion because of a queue rather than because
of the dock -- the rig returning a verdict about itself. So each pose change is
followed by a queue drain and then a scan whose `header.stamp` is later than a
clock reading taken after the change, plus one lidar period of settle.

**The robot's stillness is measured, not asserted.** Every `truth_x` depends on
it and nothing re-checked it after hundreds of poses of physics with a live
controller.

The grid deliberately runs closer than the 0.70 m gate window. Finding where
the fit stops working IS one of the measurements -- the posts leave the field
of view in the last few centimetres, and that lower bound is not assumed. It
starts at 0.08 m rather than 0.02 m because below that the sim lane cannot
measure anything: see `--distances`.

Operator steps before the first sweep
-------------------------------------
0. Confirm the two `gz` command lines on the host, the same way Step 1 pinned
   `set_pose`. This script uses `gz service -s /world/<world>/set_pose` to move
   the dock and `gz model -m <robot> -p -w <world>` to read the robot pose for
   the drift check. Neither can be exercised from a host without Gazebo, so
   they are written to fail loudly -- a bad command aborts with the captured
   `gz` output before any row is written, rather than recording rows against a
   ground truth that never happened.
1. Launch with sim time. This node pins itself to `/clock`; see `Sweeper`.

Design: docs/plans/2026-09-07-dock-detector-measurement-rig-design.md
"""

from __future__ import annotations

import argparse
import math
import re
import subprocess
import sys
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import LaserScan

from rosy_core.docking.probe import MIN_ABSENT, ProbeRow, append_row
from rosy_core.docking.profile import DockProfile, SensorOffset, fit

SCAN_QOS = QoSProfile(
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    durability=QoSDurabilityPolicy.VOLATILE,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
)

#: The sim lidar's period: `rosy_description/urdf/rosy_gz.urdf.xacro` declares
#: `<update_rate>10</update_rate>`. A pose change is followed by one period of
#: settle so the accepted frame was started after the move, not across it.
SCAN_PERIOD_S = 0.1

#: Spins used to empty the middleware queue after a pose change. Depth is 1, so
#: one is normally enough; three costs nothing and the stamp check below is the
#: guard that actually decides. Draining only saves the timeout budget.
DRAIN_SPINS = 3

#: How far the node's clock may sit from a scan stamp before the two are
#: declared different time bases. Generous: this catches "wall clock vs sim
#: clock", a gap of order 1e9 seconds, not clock jitter.
CLOCK_SKEW_MAX_S = 2.0

#: The string `gz service` prints for a successful `gz.msgs.Boolean`.
#: **Look for the positive, never for the negative.** Protobuf text format
#: omits default-valued fields, so `data: false` prints as *empty output* --
#: a check for "data: false" would catch no failure at all. A service timeout
#: is caught the same way, by this string's absence.
GZ_OK = "data: true"

#: Share of scans that may time out before the sweep is a failure rather than a
#: sweep. The old code returned success on any non-zero row count, so 559
#: timeouts and one row reported as a clean run.
TIMEOUT_SHARE_MAX = 0.02

#: Bracketed `x | y | z` triple, the shape `gz model -p` prints its pose in.
_POSE_TRIPLE = re.compile(
    r"\[\s*(-?[0-9]+(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?)\s*\|"
    r"\s*(-?[0-9]+(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?)\s*\|"
    r"\s*(-?[0-9]+(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?)\s*\]")


class SweepAborted(RuntimeError):
    """The sweep cannot produce trustworthy rows, so it produces none.

    Fitting failures are values (`ProfileFit.reason`) and timed-out scans are
    counted, because both are measurements. This is for the other kind: the
    ground truth is not what the row says it is. There is nothing to record.
    """


def _stamp_ns(scan: LaserScan) -> int:
    return scan.header.stamp.sec * 10 ** 9 + scan.header.stamp.nanosec


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sweep the dock past the robot and record fit rows.")
    parser.add_argument("--world", default="rosy_factory")
    parser.add_argument("--model", default="dock")
    parser.add_argument("--robot-model", default="rosy",
                        help="model name the robot was spawned under; "
                             "launch_sim.launch.xml spawns `rosy`")
    parser.add_argument("--out", type=Path, required=True)
    # 0.02 and 0.05 are gone. The sim lidar declares `<range><min>0.05</min>`
    # and the scanner sits at base_link x = -0.017, so at a dock x of 0.05 the
    # nearest return is 0.034 m and at 0.02 it is 0.008 m: measured on the
    # host, every ray of both poses falls under the minimum and zero returns
    # survive. Those rows would have recorded a guaranteed non-acquisition
    # caused by the sensor's own floor, in a grid whose stated purpose is
    # finding where the *fit* stops working. (Both are also outside the fit's
    # +/-0.6 rad search window at that range, so they fail twice.) 0.08 is the
    # first step that measures anything: 54 rays survive and the fit finds the
    # dock. Below 0.08 m belongs to the bench lane, which has a real sensor.
    #
    # 0.35 / 0.45 / 0.55 are new. `probe._envelope_low` refuses to report a
    # lower bound when the next grid step down is coarser than
    # `ENVELOPE_STEP_MAX_M` (0.10 m), and 0.30 -> 0.40 -> 0.50 -> 0.60 sat
    # exactly on that limit -- passing only because the comparison is `>` and
    # rounded to 6 places. A grid that reports the envelope only by exact
    # float luck is not a grid. These three halve those gaps, and the coarse
    # steps cost accuracy as well as margin: measured against `_envelope_low`
    # with a detector that acquires down to 0.45 m, the old grid reported
    # 0.500 and this one reports 0.450. That number becomes
    # `DockType.docking_threshold_m`, so the 50 mm was going into a robot.
    parser.add_argument("--distances", type=float, nargs="+",
                        default=[0.08, 0.12, 0.16, 0.20, 0.25, 0.30, 0.35,
                                 0.40, 0.45, 0.50, 0.55, 0.60, 0.68, 0.70,
                                 0.72, 0.85, 1.00])
    parser.add_argument("--laterals", type=float, nargs="+",
                        default=[-0.15, -0.08, -0.03, 0.0, 0.03, 0.08, 0.15])
    parser.add_argument("--yaws-deg", type=float, nargs="+",
                        default=[-20.0, -10.0, 0.0, 10.0, 20.0])
    # Defaulted from `probe.MIN_ABSENT` rather than retyped as 500, because
    # the two numbers mean the same thing: the design's floor for "zero false
    # positives". A copy of it here could drift below the floor silently.
    parser.add_argument("--absent-samples", type=int,
                        default=MIN_ABSENT["sim"],
                        help="scans taken with the dock parked far away; "
                             "defaults to the design's false-positive floor")
    parser.add_argument("--park-x", type=float, default=20.0)
    parser.add_argument("--drift-max-m", type=float, default=0.005,
                        help="how far the robot may move over the whole sweep")
    parser.add_argument("--scan-timeout-s", type=float, default=3.0)
    args = parser.parse_args(argv)
    if args.absent_samples < 1:
        parser.error("--absent-samples must be positive")
    for value in args.distances:
        if not math.isfinite(value) or value <= 0.0:
            parser.error(f"--distances must be finite and positive; got {value}")
    for name in ("laterals", "yaws_deg"):
        for value in getattr(args, name):
            if not math.isfinite(value):
                parser.error(f"--{name.replace('_', '-')} must be finite; "
                             f"got {value}")
    # The dock-absent phase is the false-positive evidence. If the park pose
    # leaves the dock inside the fit's window, every one of those rows is a
    # dock-present row wearing a `dock_present=False` label.
    reach = DockProfile().max_range_m
    if not math.isfinite(args.park_x) or abs(args.park_x) <= reach:
        parser.error(
            f"--park-x must be further than DockProfile.max_range_m ({reach} m) "
            f"or the dock is still in view on every dock-absent row; "
            f"got {args.park_x}")
    if not math.isfinite(args.drift_max_m) or args.drift_max_m <= 0.0:
        parser.error("--drift-max-m must be finite and positive")
    if not math.isfinite(args.scan_timeout_s) or args.scan_timeout_s <= 0.0:
        parser.error("--scan-timeout-s must be finite and positive")
    return args


def _gz(argv: list[str], what: str) -> str:
    """Run a `gz` command and hand back its stdout, or abort with everything.

    `check=True` was doing this job before and it only ever saw the exit code.
    Aborting with both streams quoted is the difference between "the sweep
    stopped" and "the sweep stopped because --model names a model this world
    does not have".
    """
    try:
        done = subprocess.run(argv, check=False, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise SweepAborted(f"{what}: `{argv[0]}` is not on PATH ({exc})") from None
    if done.returncode != 0:
        raise SweepAborted(
            f"{what}: `{' '.join(argv)}` exited {done.returncode}\n"
            f"  stdout: {done.stdout.strip()!r}\n"
            f"  stderr: {done.stderr.strip()!r}")
    return done.stdout


def set_dock_pose(world: str, model: str, x: float, y: float,
                  yaw: float) -> None:
    """Relocate the dock. Verified service name comes from Step 1.

    The reply is read, not just captured. `capture_output=True` collected the
    `gz.msgs.Boolean` and nothing looked at it, while `check=True` saw only the
    exit code -- so a wrong `--model` or `--world` answered `data: false`, or
    printed a timeout line, and the sweep went on to record hundreds of rows
    whose stated ground truth never happened. That is not a measurement error,
    it is a table of fiction, and it is indistinguishable from a real one.
    """
    request = (f'name: "{model}", position: {{x: {x}, y: {y}, z: 0.0}}, '
               f'orientation: {{x: 0.0, y: 0.0, z: {math.sin(yaw / 2.0)}, '
               f'w: {math.cos(yaw / 2.0)}}}')
    what = f"moving {model!r} to x={x} y={y} yaw={yaw}"
    reply = _gz(
        ["gz", "service", "-s", f"/world/{world}/set_pose",
         "--reqtype", "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean",
         "--timeout", "2000", "--req", request], what)
    if GZ_OK not in reply.lower():
        raise SweepAborted(
            f"{what}: the set_pose service did not report success. Expected "
            f"{GZ_OK!r} in the reply; got {reply.strip()!r} (an empty reply is "
            f"how `data: false` prints, and a timeout prints its own line). "
            f"Check --world {world!r} and --model {model!r} against the "
            f"running world.")


def parse_model_pose(text: str) -> tuple[float, float]:
    """The world (x, y) out of a `gz model -p` reply.

    Tolerant about the surrounding chatter, strict about the numbers: the first
    bracketed `x | y | z` triple at or after a line mentioning "Pose" is the
    XYZ block. Refusing to guess is the point -- a drift check that quietly
    reads 0.0 out of a reply it could not parse is worse than no drift check,
    because it certifies the very assumption it failed to test.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if "pose" not in line.lower():
            continue
        for following in lines[index:index + 4]:
            found = _POSE_TRIPLE.search(following)
            if found:
                return float(found.group(1)), float(found.group(2))
    raise SweepAborted(
        "could not read an `x | y | z` pose out of the `gz model` reply. The "
        "output format is not pinned by anything this repo can test, so it is "
        "quoted here rather than guessed at -- confirm the command in Step 0:"
        f"\n{text.strip()!r}")


def robot_pose(world: str, model: str) -> tuple[float, float]:
    """Where the robot actually is, in world coordinates."""
    return parse_model_pose(_gz(
        ["gz", "model", "-m", model, "-p", "-w", world],
        f"reading the pose of {model!r} in world {world!r}"))


class Sweeper(Node):
    def __init__(self) -> None:
        # `use_sim_time` is pinned on, and it is not a preference.
        #
        # `scan.header.stamp` is written by the simulator: `ros_gz_bridge`
        # republishes Gazebo's own message, so the stamp counts from world
        # start and is of order 1e11 ns. A node on wall time reads order 1e18
        # ns since the epoch. Comparing the two would reject every scan for
        # the whole sweep; comparing them the other way round would accept
        # every stale one. There is no reading of the code in which that
        # mismatch is harmless, so the ambiguity is removed rather than
        # documented: `dock_sweep` only ever runs against Gazebo, the node
        # takes its time from `/clock`, and both sides of the stamp comparison
        # are sim time. `check_clock_matches_stamps` then proves that at
        # runtime instead of trusting this constructor.
        #
        # The two consequences are handled explicitly. Sim time is 0 until the
        # first `/clock` arrives, and a reference of 0 would make every queued
        # frame look fresh -- so `wait_for_clock` blocks until it moves. And
        # sim time stops when the sim is paused, which would hang a sim-time
        # timeout -- so every deadline in this class is `time.monotonic`.
        super().__init__("dock_sweep", parameter_overrides=[
            Parameter("use_sim_time", Parameter.Type.BOOL, True)])
        self._scan: LaserScan | None = None
        self.create_subscription(LaserScan, "scan", self._on_scan, SCAN_QOS)

    def _on_scan(self, message: LaserScan) -> None:
        self._scan = message

    def sim_now_ns(self) -> int:
        return self.get_clock().now().nanoseconds

    def wait_for_clock(self, timeout_s: float = 10.0) -> None:
        """Block until `/clock` has moved sim time off zero."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.sim_now_ns() > 0:
                return
        raise SweepAborted(
            f"sim time is still 0 after {timeout_s} s, so `/clock` is not "
            f"reaching this node. Every scan would then look newer than the "
            f"reference and the stale-scan guard would pass everything, which "
            f"is the bug it exists to stop. Start Gazebo and check /clock is "
            f"bridged.")

    def any_scan(self, timeout_s: float = 10.0) -> LaserScan:
        """Any scan at all, stale included -- only its stamp matters here.

        Used once, before the first pose change, to prove the clock and the
        stamps share a time base. It has to be a real message: the check
        cannot be made against an assumption about what the bridge stamps.

        It also fails the sweep early when nothing publishes on `scan`, which
        used to appear as several hundred timeouts and a report of success.
        """
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self._scan is not None:
                scan, self._scan = self._scan, None
                return scan
        raise SweepAborted(
            f"no scan arrived on `scan` within {timeout_s} s, so the topic is "
            f"not publishing and there is nothing to sweep. Check the topic "
            f"name and that the lidar is enabled in the running world.")

    def check_clock_matches_stamps(self, scan: LaserScan) -> None:
        """Prove the clock and the stamps share a time base, once, up front."""
        clock_ns, stamp_ns = self.sim_now_ns(), _stamp_ns(scan)
        if abs(clock_ns - stamp_ns) > int(CLOCK_SKEW_MAX_S * 1e9):
            raise SweepAborted(
                f"the node clock reads {clock_ns / 1e9:.3f} s and the scan "
                f"stamp reads {stamp_ns / 1e9:.3f} s. They are different time "
                f"bases, so every stamp-versus-clock comparison in this sweep "
                f"is meaningless: off one way it rejects every scan, off the "
                f"other it accepts every stale one. Launch the sim with sim "
                f"time and confirm /clock and /scan come from the same "
                f"Gazebo.")

    def drain(self) -> None:
        """Empty the middleware queue. `self._scan = None` does not.

        Clearing the attribute clears Python's copy, not the DDS queue. This
        only buys back timeout budget -- the stamp check is what decides
        whether a frame is stale -- but a queued frame consumed here is a
        `spin_once` not spent on it later.
        """
        for _ in range(DRAIN_SPINS):
            rclpy.spin_once(self, timeout_sec=0.0)
        self._scan = None

    def next_scan_newer_than(self, required_ns: int,
                             timeout_s: float = 3.0) -> LaserScan | None:
        """A scan whose own stamp is strictly later than `required_ns`.

        The settle margin is the caller's to add, because its reason is the
        caller's: a frame stamped within one lidar period of a pose change may
        have been rendered across the move, and a scan of a dock caught
        mid-teleport is a scan of neither pose. Nothing needs settling between
        two frames of a scene that is standing still.
        """
        self.drain()
        # Wall clock, deliberately: a paused sim freezes sim time and this
        # loop would never end.
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            scan, self._scan = self._scan, None
            if scan is not None and _stamp_ns(scan) > required_ns:
                return scan
        return None


def _row(scan, profile, sensor, present, x, y, yaw, now):
    """One row. A scan that produced no fit is a recorded row, not a gap."""
    got = fit(scan.ranges, scan.angle_min, scan.angle_increment,
              profile, sensor, now)
    observation = got.observation
    return ProbeRow(
        lane="sim", candidate="geometry", dock_present=present,
        truth_x=x, truth_y=y, truth_yaw=yaw,
        fit_x=None if observation is None else observation.x,
        fit_y=None if observation is None else observation.y,
        fit_yaw=None if observation is None else observation.yaw,
        residual=got.residual_m, points=got.points,
        confidence=None if observation is None else observation.confidence)


def _capture(node, args, profile, sensor, required_ns, present,
             x, y, yaw) -> int | None:
    """Take one scan newer than `required_ns` and append one row.

    Returns the accepted scan's stamp so the caller can chain it, or None when
    the scan timed out. `now` reaches `DockObservation.at` and the row never
    records it, so the old `float(written + index)` was arithmetic on a
    counter that also incremented -- double-counting a value nothing read. The
    scan's own stamp is the honest answer and it is already in hand.
    """
    scan = node.next_scan_newer_than(required_ns, args.scan_timeout_s)
    if scan is None:
        return None
    stamp_ns = _stamp_ns(scan)
    append_row(args.out, _row(scan, profile, sensor, present, x, y, yaw,
                              stamp_ns / 1e9))
    return stamp_ns


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    profile = DockProfile()
    sensor = SensorOffset()

    rclpy.init()
    node = Sweeper()
    written = skipped = 0
    try:
        node.wait_for_clock()
        # Both up-front refusals, before a single row exists: `scan` must be
        # publishing, and its stamps must share a time base with the clock the
        # freshness check compares them against.
        node.check_clock_matches_stamps(node.any_scan())
        # The robot's stillness is the premise of every `truth_x` in the
        # table, so it is read before the first pose and again after the last.
        started_at = robot_pose(args.world, args.robot_model)

        settle_ns = int(SCAN_PERIOD_S * 1e9)
        for distance in args.distances:
            for lateral in args.laterals:
                for yaw_deg in args.yaws_deg:
                    yaw = math.radians(yaw_deg)
                    # World yaw is the truth yaw, NOT pi + yaw. The robot sits
                    # at the origin facing +x and meets the dock's -x face, so
                    # the dock's axes already line up with the world's. Adding
                    # pi mirrors the lateral axis, which flips the asymmetric
                    # post pattern and makes the residual gate reject every
                    # single sample.
                    set_dock_pose(args.world, args.model,
                                  distance, lateral, yaw)
                    # Read *after* the service returns, or the reference
                    # cannot separate the new pose from the old one.
                    moved_at = node.sim_now_ns()
                    if _capture(node, args, profile, sensor,
                                moved_at + settle_ns,
                                True, distance, lateral, yaw) is None:
                        skipped += 1
                    else:
                        written += 1

        # The dock is parked once, not once per sample -- but every one of
        # these rows still has to postdate the park, because this is the
        # false-positive evidence and one stale pre-park frame is one false
        # positive. The reference then rolls forward onto each accepted stamp
        # so the 500 rows are 500 distinct frames rather than however many
        # frames happened to be sitting in the queue.
        set_dock_pose(args.world, args.model, args.park_x, 0.0, 0.0)
        required_ns = node.sim_now_ns() + settle_ns
        # Unlike a grid point, a timed-out absent sample is worth retrying:
        # there is no pose to re-establish, only another frame of a scene that
        # is standing still. And it has to be retried, because
        # `--absent-samples` defaults to `probe.MIN_ABSENT["sim"]` exactly:
        # a handful of timeouts, well inside the ceiling below, would leave
        # the table short of the design's false-positive floor, and the
        # verdict would then fail on how little was measured while this
        # script reported success.
        absent = attempts = 0
        allowance = args.absent_samples + max(10, args.absent_samples // 20)
        while absent < args.absent_samples and attempts < allowance:
            attempts += 1
            stamp_ns = _capture(node, args, profile, sensor, required_ns,
                                False, math.nan, math.nan, math.nan)
            if stamp_ns is None:
                skipped += 1
                continue
            absent += 1
            written += 1
            # Roll the reference onto the accepted stamp so these are N
            # distinct frames and not one frame counted N times.
            required_ns = stamp_ns
        if absent < args.absent_samples:
            raise SweepAborted(
                f"only {absent} of the {args.absent_samples} dock-absent "
                f"scans arrived, in {attempts} attempts. That count is the "
                f"design's false-positive floor (probe.MIN_ABSENT['sim']), so "
                f"a short table fails the verdict on how little was measured "
                f"rather than on what the detector did.")

        ended_at = robot_pose(args.world, args.robot_model)
    except SweepAborted as exc:
        print(f"FAIL {exc}\n     {written} rows had been written to "
              f"{args.out} and {skipped} scans had timed out when the sweep "
              f"stopped.", file=sys.stderr)
        return 1
    finally:
        node.destroy_node()
        rclpy.shutdown()

    drift = math.hypot(ended_at[0] - started_at[0],
                       ended_at[1] - started_at[1])
    attempted = written + skipped
    share = skipped / attempted if attempted else 1.0
    print(f"wrote {written} rows to {args.out}; {skipped} of {attempted} "
          f"scans timed out ({share:.1%}); robot drift {drift * 1000:.1f} mm")

    if drift > args.drift_max_m:
        print(f"FAIL the robot moved {drift * 1000:.1f} mm during the sweep, "
              f"over the {args.drift_max_m * 1000:.1f} mm ceiling: started at "
              f"{started_at}, ended at {ended_at}. Every truth_x in "
              f"{args.out} is measured from a robot that was supposed to be "
              f"still, and the drift cannot be attributed to particular rows, "
              f"so the whole table is suspect.", file=sys.stderr)
        return 1
    if not written:
        print(f"FAIL no rows were written to {args.out}", file=sys.stderr)
        return 1
    if share > TIMEOUT_SHARE_MAX:
        print(f"FAIL {skipped} of {attempted} scans timed out ({share:.1%}), "
              f"over the {TIMEOUT_SHARE_MAX:.0%} ceiling. {written} rows were "
              f"written and they may be fine, but a sweep that missed this "
              f"much did not measure the grid it claims to have measured.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
