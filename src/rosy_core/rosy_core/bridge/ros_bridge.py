"""rosy_core.bridge.ros_bridge — ROS-101 모든 ROS I/O 집중 (P1-3).

- 유일한 cmd_vel 퍼블리셔 (D-2): 50 Hz select_output → publish
- 구독: odom / battery/voltage / nav_cmd_vel(Nav2 출력 리매핑 입력)
- Nav2 NavigateToPose 액션 클라이언트 (NavExecutor 구현)
- TF: map → base pose 조회 (frame_prefix 반영, §6.1)
"""

from __future__ import annotations

import math
from typing import Optional

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from nav_msgs.msg import Odometry
from nav2_msgs.action import NavigateToPose
from std_msgs.msg import Float32
import tf2_ros
from tf2_ros import Buffer, TransformListener

from rosy_core.command.manager import Twist as CoreTwist
from rosy_core.navigation.manager import NavGoalSpec


class RosBridge:
    def __init__(self, node: Node, services) -> None:
        self._node = node
        self._svc = services
        cfg = services.config
        self._frame_prefix = str(cfg.get("robot", {}).get("frame_prefix", ""))
        self._base_frame = f"{self._frame_prefix}base_footprint"
        self._map_frame = "map"
        self._battery_full = float(cfg.get("safety", {}).get("battery_full_voltage", 12.6))
        self._battery_empty = float(cfg.get("safety", {}).get("battery_empty_voltage", 10.0))
        self._state_hz = float(cfg.get("state", {}).get("rate_hz", 10.0))

        self.cmd_vel_pub = node.create_publisher(Twist, "cmd_vel", 10)
        self.initialpose_pub = node.create_publisher(
            PoseWithCovarianceStamped, "initialpose", 10)

        self.nav_client = ActionClient(node, NavigateToPose, "navigate_to_pose")
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, node)

        node.create_subscription(Odometry, "odom", self._on_odom, 10)
        node.create_subscription(Float32, "battery/voltage", self._on_battery, 10)
        node.create_subscription(Twist, "nav_cmd_vel", self._on_nav_cmd_vel, 10)

        self._cmd_timer = node.create_timer(1.0 / 50.0, self._publish_cmd_vel)
        self._state_timer = node.create_timer(1.0 / self._state_hz, self._tick_state)

        self._goal_handle = None
        self._svc.nav.executor = self
        self._node.get_logger().info("ros_bridge ready (cmd_vel sole publisher @50Hz)")

    def _on_odom(self, msg: Odometry) -> None:
        pose = msg.pose.pose
        yaw = math.atan2(
            2.0 * (pose.orientation.w * pose.orientation.z + pose.orientation.x * pose.orientation.y),
            1.0 - 2.0 * (pose.orientation.y ** 2 + pose.orientation.z ** 2),
        )
        self._svc.state.set_pose(pose.position.x, pose.position.y, yaw)
        self._svc.state.set_velocity(msg.twist.twist.linear.x, msg.twist.twist.angular.z)
        self._svc.nav.on_pose_progress(pose.position.x, pose.position.y)

    def _on_battery(self, msg: Float32) -> None:
        voltage = float(msg.data)
        span = max(self._battery_full - self._battery_empty, 1e-6)
        percent = max(0.0, min(100.0, (voltage - self._battery_empty) / span * 100.0))
        self._svc.state.set_battery(percent, voltage)
        action = self._svc.safety.on_battery_percent(percent)
        if action == "RETURN_HOME":
            try:
                self._svc.nav.home(source="battery_policy")
            except Exception:
                self._svc.safety.trigger_estop("battery_policy")
        elif action in ("STOP",):
            self._svc.safety.trigger_estop("battery_policy")

    def _on_nav_cmd_vel(self, msg: Twist) -> None:
        self._svc.command.set_nav_twist(CoreTwist(linear=msg.linear.x, angular=msg.angular.z))

    def _publish_cmd_vel(self) -> None:
        out = self._svc.command.select_output()
        msg = Twist()
        msg.linear.x = out.linear
        msg.angular.z = out.angular
        self.cmd_vel_pub.publish(msg)

    def _tick_state(self) -> None:
        try:
            tf = self.tf_buffer.lookup_transform(
                self._map_frame, self._base_frame, rclpy.time.Time())
            t = tf.transform.translation
            q = tf.transform.rotation
            yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y ** 2 + q.z ** 2))
            self._svc.state.set_pose(t.x, t.y, yaw)
        except tf2_ros.TransformException:
            pass
        self._svc.state.snapshot()

    # --- NavExecutor 구현 (navigation.manager와 계약) -------------------------

    def send_goal(self, spec: NavGoalSpec) -> None:
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = spec.frame
        goal.pose.header.stamp = self._node.get_clock().now().to_msg()
        goal.pose.pose.position.x = spec.x
        goal.pose.pose.position.y = spec.y
        goal.pose.pose.orientation.z = math.sin(spec.yaw / 2.0)
        goal.pose.pose.orientation.w = math.cos(spec.yaw / 2.0)
        if not self.nav_client.wait_for_server(timeout_sec=0.0):
            self._node.get_logger().warn("navigate_to_pose server not ready; goal queued anyway")
        future = self.nav_client.send_goal_async(goal)
        future.add_done_callback(self._goal_response_cb)

    def _goal_response_cb(self, future) -> None:
        goal_handle = future.result()
        if goal_handle is None or not goal_handle.accepted:
            self._svc.nav.on_result(False, "REJECTED")
            return
        self._goal_handle = goal_handle
        self._svc.nav.on_goal_accepted()
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._result_cb)

    def _result_cb(self, future) -> None:
        self._goal_handle = None
        if self._svc.nav.nav_state.value == "CANCELED":
            return
        try:
            result = future.result()
            self._svc.nav.on_result(result.status == 4)
        except Exception as exc:
            self._svc.nav.on_result(False, str(exc))

    def cancel_goal(self) -> None:
        if self._goal_handle is not None:
            self._goal_handle.cancel_goal_async()
            self._goal_handle = None
            self._node.get_logger().info("navigation cancel requested")

    def send_initial_pose(self, x: float, y: float, yaw: float) -> None:
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = self._map_frame
        msg.header.stamp = self._node.get_clock().now().to_msg()
        msg.pose.pose.position.x = x
        msg.pose.pose.position.y = y
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        self.initialpose_pub.publish(msg)
