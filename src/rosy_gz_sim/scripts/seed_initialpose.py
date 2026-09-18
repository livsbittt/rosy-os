#!/usr/bin/env python3
"""Publish map-frame initialpose at gz_multi spawn (D-115).

rclpy lives here, not in world_profiles. Host pytest must not import this file.
"""

from __future__ import annotations

import math

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node


class SeedInitialPose(Node):
    def __init__(self) -> None:
        super().__init__("seed_initialpose")
        self.declare_parameter("x", 0.0)
        self.declare_parameter("y", 0.0)
        self.declare_parameter("yaw", 0.0)
        self.declare_parameter("count", 30)
        self.declare_parameter("period_s", 0.5)
        self._pub = self.create_publisher(PoseWithCovarianceStamped, "initialpose", 10)
        self._left = int(self.get_parameter("count").value)
        period = float(self.get_parameter("period_s").value)
        self._timer = self.create_timer(period, self._tick)

    def _tick(self) -> None:
        x = float(self.get_parameter("x").value)
        y = float(self.get_parameter("y").value)
        yaw = float(self.get_parameter("yaw").value)
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = "map"
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.pose.pose.position.x = x
        msg.pose.pose.position.y = y
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        cov = [0.0] * 36
        cov[0] = 0.25
        cov[7] = 0.25
        cov[35] = math.radians(15.0) ** 2
        msg.pose.covariance = cov
        self._pub.publish(msg)
        self._left -= 1
        if self._left <= 0:
            self.get_logger().info(f"seeded initialpose map ({x:.3f}, {y:.3f})")
            self._timer.cancel()


def main() -> None:
    rclpy.init()
    node = SeedInitialPose()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
