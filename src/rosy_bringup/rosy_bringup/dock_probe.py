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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture one dock measurement row. Reads only.")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--candidate", choices=CANDIDATES, required=True)
    parser.add_argument("--ambient", choices=AMBIENT_BANDS, required=True)
    parser.add_argument("--distance", type=float,
                        help="measured dock distance, m; omit with --no-dock")
    parser.add_argument("--lateral", type=float, default=0.0)
    parser.add_argument("--yaw-deg", type=float, default=0.0)
    parser.add_argument("--no-dock", action="store_true",
                        help="nothing in front: sets the false-positive and "
                             "ambient-floor rows")
    parser.add_argument("--int-target", type=float,
                        help="mean intensity over the retroreflective half")
    parser.add_argument("--int-baseline", type=float,
                        help="mean intensity over the matte half")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args(argv)

    if args.no_dock:
        if args.distance is not None:
            parser.error("--distance makes no sense with --no-dock")
    elif args.distance is None:
        parser.error("--distance is required unless --no-dock is given")
    elif args.distance <= 0.0:
        parser.error("--distance must be positive")

    if args.candidate == "intensity" and not args.no_dock:
        if args.int_target is None or args.int_baseline is None:
            parser.error("the intensity candidate needs both --int-target "
                         "and --int-baseline")
    if args.timeout <= 0.0:
        parser.error("--timeout must be positive")
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
        lane="bench", candidate=args.candidate, dock_present=present,
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
