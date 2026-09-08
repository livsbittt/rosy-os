#!/usr/bin/env python3
"""Read-only dock measurement probe.

One invocation captures one sample: the latest `/scan` and `/ir_sensor/range`,
labelled with a ground truth the operator measured with a ruler, appended as
one row to the shared CSV.

The probe never publishes `cmd_vel`, never enables torque, and never commands
the dock. D-2 keeps the Command Manager as the only legal publisher of
`cmd_vel`, and this tool has no reason to be an exception.

A missing message is a recorded blank, not a crash. A sweep that dies halfway
throws away an expensive physical experiment.

**A refused argument is cheap; a silently mislabelled row is not.** This is the
tool an operator drives by hand while kneeling next to a robot with a ruler, so
every ground truth is validated before a node is even created: non-finite values
are refused because NaN satisfies every `<=` comparison downstream and would be
recorded as a truth nobody measured, and each value must fall inside a bound the
rig can mean something at. The rejected alternative was clamping to the nearest
legal value, which turns a typo into a plausible row -- the one outcome this
whole rig exists to avoid.

Ground truth that `--no-dock` does not have is refused rather than accepted and
dropped. `--no-dock --lateral 5.0` used to parse and then write blanks, so the
operator's belief about what was recorded and what was recorded disagreed with
no diagnostic anywhere.

Design: docs/plans/2026-09-07-dock-detector-measurement-rig-design.md
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import LaserScan
from std_msgs.msg import UInt16MultiArray

from rosy_core.docking.probe import ProbeRow, append_row
from rosy_core.docking.profile import DockProfile, SensorOffset, fit

BEST_EFFORT = QoSProfile(
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    durability=QoSDurabilityPolicy.VOLATILE,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
)

AMBIENT_BANDS = ("dark", "indoor", "direct-sun")
CANDIDATES = ("geometry", "intensity", "ir")

#: The lane this script writes. `probe.LANES` declares the only two lanes the
#: verdict can apply a sample floor to, and `verdict()` groups by (candidate,
#: lane): a lane string it does not recognise fails its own verdict instead of
#: being averaged into the sim numbers. Keep this equal to `probe.LANES[1]`.
LANE = "bench"

#: Plausibility bounds on the ruler-measured truth. These are typo catchers,
#: not physics -- but every one of them is anchored to something real, because
#: a bound nobody can justify gets widened the first time it is inconvenient.
#:
#: Distance: past `DockProfile.max_range_m` the fit discards every return by
#: construction, so a row labelled further away records the profile's config
#: rather than the detector's reach. The lower end stays open above zero: the
#: bench deliberately measures down to 0.03 m for the IR onset.
DISTANCE_MAX_M = DockProfile().max_range_m
#: Lateral: at the 0.70 m gate range the fit's +/-0.6 rad search window spans
#: about +/-0.48 m, so a dock further off-axis than this is outside the window
#: at every distance the rig measures.
LATERAL_MAX_M = 0.50
#: Yaw: a robot meeting the dock's face cannot be past a quarter turn from it,
#: and a value outside this is a degrees/radians mix-up, which is the mistake
#: this argument actually invites.
YAW_MAX_DEG = 90.0
#: Timeout: `/scan` publishes at 10 Hz. A wait longer than this is not a slow
#: topic, it is the wrong topic, and the operator should hear that in seconds.
TIMEOUT_MAX_S = 60.0


def _finite(text: str) -> float:
    """`float`, minus the two values that pass every check downstream.

    `--distance nan` used to be accepted: `args.distance <= 0.0` is False for
    NaN, so the positivity check waved it through and the CSV recorded a ruler
    reading of NaN. `--timeout nan` got further still and died inside
    `collect()` on `int(float('nan'))`, after `rclpy.init()`, with a traceback
    instead of a usage message.
    """
    try:
        value = float(text)
    except ValueError:
        # Raised as ArgumentTypeError rather than left to argparse so the
        # message says what was wrong instead of naming this function.
        raise argparse.ArgumentTypeError(f"{text!r} is not a number") from None
    if not math.isfinite(value):
        raise argparse.ArgumentTypeError(
            f"{text!r} is not a finite number; NaN and inf satisfy the "
            f"comparisons below and would be recorded as measured truth")
    return value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture one dock measurement row. Reads only.")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--candidate", choices=CANDIDATES, required=True)
    parser.add_argument("--ambient", choices=AMBIENT_BANDS, required=True)
    parser.add_argument("--distance", type=_finite,
                        help="measured dock distance, m; omit with --no-dock")
    # Default None, not 0.0, so `--no-dock --lateral 0.0` can be told apart
    # from `--no-dock`. Without that distinction the refusal below cannot
    # exist, and the value was silently discarded instead.
    parser.add_argument("--lateral", type=_finite, default=None)
    parser.add_argument("--yaw-deg", type=_finite, default=None)
    parser.add_argument("--no-dock", action="store_true",
                        help="nothing in front: sets the false-positive and "
                             "ambient-floor rows")
    parser.add_argument("--int-target", type=_finite,
                        help="mean intensity over the retroreflective half")
    parser.add_argument("--int-baseline", type=_finite,
                        help="mean intensity over the matte half")
    parser.add_argument("--timeout", type=_finite, default=5.0)
    args = parser.parse_args(argv)

    if args.no_dock:
        # Every pose field is a blank on a dock-absent row, so any of them
        # given here is a belief about the row that the row will not hold.
        for flag, value in (("--distance", args.distance),
                            ("--lateral", args.lateral),
                            ("--yaw-deg", args.yaw_deg)):
            if value is not None:
                parser.error(f"{flag} makes no sense with --no-dock; the row "
                             f"records a blank pose, so this value would be "
                             f"discarded rather than measured")
        args.lateral = args.yaw_deg = 0.0
    else:
        if args.distance is None:
            parser.error("--distance is required unless --no-dock is given")
        if not 0.0 < args.distance <= DISTANCE_MAX_M:
            parser.error(
                f"--distance must be above 0 and at most {DISTANCE_MAX_M} m "
                f"(DockProfile.max_range_m); the fit discards every return "
                f"past it, so {args.distance} m cannot be measured here")
        if args.lateral is None:
            args.lateral = 0.0
        if abs(args.lateral) > LATERAL_MAX_M:
            parser.error(
                f"--lateral must be within +/-{LATERAL_MAX_M} m; "
                f"{args.lateral} m is outside the fit's search window at "
                f"every distance this rig measures")
        if args.yaw_deg is None:
            args.yaw_deg = 0.0
        if abs(args.yaw_deg) > YAW_MAX_DEG:
            parser.error(
                f"--yaw-deg must be within +/-{YAW_MAX_DEG} degrees; "
                f"{args.yaw_deg} is a degrees/radians mix-up, not a pose")

    if args.candidate == "intensity" and not args.no_dock:
        if args.int_target is None or args.int_baseline is None:
            parser.error("the intensity candidate needs both --int-target "
                         "and --int-baseline")
    for flag, value in (("--int-target", args.int_target),
                        ("--int-baseline", args.int_baseline)):
        # A mean over a set of non-negative intensities cannot be negative,
        # and the intensity verdict compares these two directly.
        if value is not None and value < 0.0:
            parser.error(f"{flag} is a mean intensity and cannot be negative, "
                         f"but is {value}")

    if not 0.0 < args.timeout <= TIMEOUT_MAX_S:
        parser.error(
            f"--timeout must be above 0 and at most {TIMEOUT_MAX_S} s; "
            f"/scan runs at 10 Hz, so a longer wait is the wrong topic")
    return args


class Probe(Node):
    def __init__(self) -> None:
        super().__init__("dock_probe")
        self.scan: LaserScan | None = None
        self.infrared: UInt16MultiArray | None = None
        self.create_subscription(LaserScan, "scan", self._on_scan, BEST_EFFORT)
        self.create_subscription(UInt16MultiArray, "ir_sensor/range",
                                 self._on_ir, BEST_EFFORT)

    def _on_scan(self, message: LaserScan) -> None:
        self.scan = message

    def _on_ir(self, message: UInt16MultiArray) -> None:
        self.infrared = message

    def collect(self, timeout_s: float) -> None:
        deadline = self.get_clock().now().nanoseconds + int(timeout_s * 1e9)
        while self.get_clock().now().nanoseconds < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.scan is not None and self.infrared is not None:
                return


def build_row(args: argparse.Namespace, scan, infrared) -> ProbeRow:
    present = not args.no_dock
    truth_x = math.nan if args.no_dock else args.distance
    truth_y = math.nan if args.no_dock else args.lateral
    truth_yaw = math.nan if args.no_dock else math.radians(args.yaw_deg)

    observation = residual = points = None
    if scan is not None:
        got = fit(scan.ranges, scan.angle_min, scan.angle_increment,
                  DockProfile(), SensorOffset(), now=0.0)
        observation, residual, points = got.observation, got.residual_m, got.points

    channels = list(infrared.data) if infrared is not None else []
    while len(channels) < 3:
        channels.append(None)

    return ProbeRow(
        lane=LANE, candidate=args.candidate, dock_present=present,
        truth_x=truth_x, truth_y=truth_y, truth_yaw=truth_yaw,
        ambient=args.ambient,
        fit_x=None if observation is None else observation.x,
        fit_y=None if observation is None else observation.y,
        fit_yaw=None if observation is None else observation.yaw,
        residual=residual, points=points,
        confidence=None if observation is None else observation.confidence,
        int_target=args.int_target, int_baseline=args.int_baseline,
        ir_l=channels[0], ir_mid=channels[1], ir_r=channels[2])


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rclpy.init()
    node = Probe()
    try:
        node.collect(args.timeout)
        if node.scan is None:
            node.get_logger().warn("no scan arrived; recording a blank fit")
        if node.infrared is None:
            node.get_logger().warn("no ir_sensor/range arrived; recording blanks")
        row = build_row(args, node.scan, node.infrared)
        append_row(args.out, row)
        node.get_logger().info(
            f"appended {args.candidate}/{args.ambient} row to {args.out}")
    finally:
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
