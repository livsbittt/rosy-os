#!/usr/bin/env python3
"""Gazebo sweep for the dock detector rig.

Moves the dock over a ground-truth grid, samples one scan per pose, runs the
ROS-free fit, and appends a row per sample. The robot never moves: teleporting
it fights the controller, while relocating a static model is exact and free.

Ground truth is exact here, which is the whole reason this lane can afford
hundreds of samples where the bench affords tens.

The grid deliberately runs closer than the 0.70 m gate window. Finding where
the fit stops working IS one of the measurements -- the posts leave the field
of view in the last few centimetres, and that lower bound is not assumed.

Design: docs/plans/2026-09-07-dock-detector-measurement-rig-design.md
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import LaserScan

from rosy_core.docking.probe import ProbeRow, append_row
from rosy_core.docking.profile import DockProfile, SensorOffset, fit

SCAN_QOS = QoSProfile(
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    durability=QoSDurabilityPolicy.VOLATILE,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sweep the dock past the robot and record fit rows.")
    parser.add_argument("--world", default="rosy_factory")
    parser.add_argument("--model", default="dock")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--distances", type=float, nargs="+",
                        default=[0.02, 0.05, 0.08, 0.12, 0.16, 0.20, 0.25,
                                 0.30, 0.40, 0.50, 0.60, 0.68, 0.70, 0.72,
                                 0.85, 1.00])
    parser.add_argument("--laterals", type=float, nargs="+",
                        default=[-0.15, -0.08, -0.03, 0.0, 0.03, 0.08, 0.15])
    parser.add_argument("--yaws-deg", type=float, nargs="+",
                        default=[-20.0, -10.0, 0.0, 10.0, 20.0])
    parser.add_argument("--absent-samples", type=int, default=500,
                        help="scans taken with the dock parked far away")
    parser.add_argument("--park-x", type=float, default=20.0)
    args = parser.parse_args(argv)
    if args.absent_samples < 1:
        parser.error("--absent-samples must be positive")
    return args


def set_dock_pose(world: str, model: str, x: float, y: float,
                  yaw: float) -> None:
    """Relocate the dock. Verified service name comes from Step 1."""
    request = (f'name: "{model}", position: {{x: {x}, y: {y}, z: 0.0}}, '
               f'orientation: {{x: 0.0, y: 0.0, z: {math.sin(yaw / 2.0)}, '
               f'w: {math.cos(yaw / 2.0)}}}')
    subprocess.run(
        ["gz", "service", "-s", f"/world/{world}/set_pose",
         "--reqtype", "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean",
         "--timeout", "2000", "--req", request],
        check=True, capture_output=True, text=True)


class Sweeper(Node):
    def __init__(self) -> None:
        super().__init__("dock_sweep")
        self._scan: LaserScan | None = None
        self.create_subscription(LaserScan, "scan", self._on_scan, SCAN_QOS)

    def _on_scan(self, message: LaserScan) -> None:
        self._scan = message

    def next_scan(self, timeout_s: float = 3.0) -> LaserScan | None:
        self._scan = None
        deadline = self.get_clock().now().nanoseconds + int(timeout_s * 1e9)
        while self.get_clock().now().nanoseconds < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self._scan is not None:
                return self._scan
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    profile = DockProfile()
    sensor = SensorOffset()

    rclpy.init()
    node = Sweeper()
    written = skipped = 0
    try:
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
                    set_dock_pose(args.world, args.model, distance, lateral, yaw)
                    scan = node.next_scan()
                    if scan is None:
                        skipped += 1
                        continue
                    now = float(written)
                    append_row(args.out, _row(scan, profile, sensor, True,
                                              distance, lateral, yaw, now))
                    written += 1

        set_dock_pose(args.world, args.model, args.park_x, 0.0, 0.0)
        for index in range(args.absent_samples):
            scan = node.next_scan()
            if scan is None:
                skipped += 1
                continue
            append_row(args.out, _row(scan, profile, sensor, False,
                                      math.nan, math.nan, math.nan,
                                      float(written + index)))
            written += 1
    finally:
        node.destroy_node()
        rclpy.shutdown()

    print(f"wrote {written} rows to {args.out}; {skipped} scans timed out")
    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(main())
