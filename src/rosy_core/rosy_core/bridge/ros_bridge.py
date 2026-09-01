"""rosy_core.bridge.ros_bridge — ROS-101 모든 ROS I/O 집중 (P1-3).

- 유일한 cmd_vel 퍼블리셔 (D-2): 50 Hz select_output → publish
- 구독: odom / battery/voltage / nav_cmd_vel(Nav2 출력 리매핑 입력)
       / us_sensor/range, batt_state (PWR-002 근접 웨이크·배터리 표시)
- 발행: power/mode, display/info (PWR-003) — LED는 set_led 서비스로 구동
- Nav2 NavigateToPose 액션 클라이언트 (NavExecutor 구현)
- TF: map → base pose 조회 (frame_prefix 반영, §6.1)
"""

from __future__ import annotations

import json
import math
import hashlib
import socket
import threading
import time
from pathlib import Path
from typing import Optional

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from nav_msgs.msg import Odometry
from nav2_msgs.action import NavigateToPose
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import BatteryState, Imu, LaserScan, Range
from slam_toolbox.srv import SaveMap
from std_msgs.msg import Float32, String

from rosy_interfaces.srv import SetLed
import tf2_ros
from tf2_ros import Buffer, TransformListener

from rosy_core.command.manager import Twist as CoreTwist
from rosy_core.diagnostics.collector import (
    CpuLoadProvider,
    DiagnosticsCollector,
    MemoryAvailableProvider,
    disk_provider,
    topic_freshness_provider,
)
from rosy_core.navigation.manager import NavGoalSpec
from rosy_core.protocol.schemas import HealthState

# 늦게 뜬 노드도 현재 모드를 즉시 받도록 latch 한다 (PWR-003).
_LATCHED = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                      durability=DurabilityPolicy.TRANSIENT_LOCAL)

# 정보 창이 열려 있는 동안 display/info 재발행 간격 (s).
_INFO_REPUBLISH_S = 1.0

# 배터리 잔량 → LED 색 (percent 하한, R, G, B).
_LED_STEPS = ((60.0, 0, 60, 0), (30.0, 60, 40, 0), (0.0, 60, 0, 0))


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
        node.create_subscription(LaserScan, "scan", self._on_scan, 10)
        node.create_subscription(Imu, "imu_raw", self._on_imu, 10)
        node.create_subscription(Range, "us_sensor/range", self._on_us_range, 10)
        node.create_subscription(BatteryState, "batt_state", self._on_batt_state, 10)

        self.power_mode_pub = node.create_publisher(String, "power/mode", _LATCHED)
        self.display_info_pub = node.create_publisher(String, "display/info", 10)
        self._led_client = node.create_client(SetLed, "set_led")

        self._cmd_timer = node.create_timer(1.0 / 50.0, self._publish_cmd_vel)
        self._state_timer = node.create_timer(1.0 / self._state_hz, self._tick_state)
        self._diag_timer = node.create_timer(1.0, self._tick_diagnostics)
        self._power_timer = node.create_timer(1.0 / 5.0, self._tick_power)

        self._goal_handle = None
        self._last_odom_ts = 0.0
        self._slam_client = node.create_client(SaveMap, "slam_toolbox/save_map")

        self._published_power_mode: Optional[str] = None
        self._info_was_visible = False
        self._info_last_pub = 0.0
        self._voltage_topic_seen = False
        self._api_address: Optional[str] = None

        self._setup_diagnostics()
        self._svc.nav.executor = self
        self._node.get_logger().info("ros_bridge ready (cmd_vel sole publisher @50Hz)")

    def _on_odom(self, msg: Odometry) -> None:
        self._last_odom_ts = time.monotonic()
        pose = msg.pose.pose
        yaw = math.atan2(
            2.0 * (pose.orientation.w * pose.orientation.z + pose.orientation.x * pose.orientation.y),
            1.0 - 2.0 * (pose.orientation.y ** 2 + pose.orientation.z ** 2),
        )
        self._svc.state.set_pose(pose.position.x, pose.position.y, yaw)
        self._svc.state.set_velocity(msg.twist.twist.linear.x, msg.twist.twist.angular.z)
        self._svc.nav.on_pose_progress(pose.position.x, pose.position.y)

    def _on_battery(self, msg: Float32) -> None:
        self._voltage_topic_seen = True
        self._apply_voltage(float(msg.data))

    def _apply_voltage(self, voltage: float) -> None:
        if not math.isfinite(voltage):
            return
        span = max(self._battery_full - self._battery_empty, 1e-6)
        percent = max(0.0, min(100.0, (voltage - self._battery_empty) / span * 100.0))
        self._svc.state.set_battery(percent, voltage)
        self._svc.power.on_battery_alert(self._battery_alert_state(percent))
        action = self._svc.safety.on_battery_percent(percent)
        if action == "RETURN_HOME":
            try:
                self._svc.nav.home(source="battery_policy")
            except Exception:
                self._svc.safety.trigger_estop("battery_policy")
        elif action in ("STOP",):
            self._svc.safety.trigger_estop("battery_policy")

    def _battery_alert_state(self, percent: float) -> str:
        """SAF-005 임계와 동일한 구간 판정 — 경보 시 화면을 깨우기 위한 입력."""
        policy = self._svc.safety.battery_policy
        if percent <= policy.critical_percent:
            return "critical"
        if percent <= policy.warning_percent:
            return "warning"
        return "ok"

    def _on_nav_cmd_vel(self, msg: Twist) -> None:
        self._svc.command.set_nav_twist(CoreTwist(linear=msg.linear.x, angular=msg.angular.z))

    def _publish_cmd_vel(self) -> None:
        out = self._svc.command.select_output()
        if out.linear != 0.0 or out.angular != 0.0:
            # 절전 정책은 모터 경로에 개입하지 않는다. 명령이 나가는 것을
            # 관측만 하고 센서·화면을 즉시 ACTIVE로 되돌린다 (안전 인터록).
            self._svc.power.on_activity("cmd_vel")
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
        snapshot = self._svc.state.snapshot()
        # 로봇 모드가 IDLE이 아니면 절전 진입을 막는다 (PWR-001 안전 인터록).
        self._svc.power.on_robot_mode(snapshot.mode)

    def _on_scan(self, msg: LaserScan) -> None:
        self._svc.state.set_sensor("lidar", {
            "frame_id": msg.header.frame_id,
            "range_min": msg.range_min,
            "range_max": msg.range_max,
            "angle_min": msg.angle_min,
            "angle_max": msg.angle_max,
            "num_ranges": len(msg.ranges),
            "ranges": list(msg.ranges),
            "received_at": time.time(),
        })

    def _on_imu(self, msg: Imu) -> None:
        q = msg.orientation
        yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y ** 2 + q.z ** 2))
        self._svc.state.set_sensor("imu", {
            "orientation_yaw": yaw,
            "angular_velocity_z": msg.angular_velocity.z,
            "linear_accel_x": msg.linear_acceleration.x,
            "received_at": time.time(),
        })

    # --- PWR-002~004 근접 웨이크 --------------------------------------------

    def _on_us_range(self, msg: Range) -> None:
        range_m = float(msg.range)
        self._svc.state.set_sensor("ultrasonic", {
            "frame_id": msg.header.frame_id,
            "range": range_m,
            "min_range": msg.min_range,
            "max_range": msg.max_range,
            "field_of_view": msg.field_of_view,
            "received_at": time.time(),
        })
        # 센서가 스스로 보고한 유효 구간 밖 표본은 정책에 넣지 않는다.
        if math.isfinite(range_m) and msg.min_range <= range_m <= msg.max_range:
            self._svc.power.on_range(range_m)

    def _on_batt_state(self, msg: BatteryState) -> None:
        voltage = float(msg.voltage)
        self._svc.state.set_sensor("battery", {
            "voltage": voltage,
            "percentage": float(msg.percentage),
            "power_supply_status": int(msg.power_supply_status),
            "location": msg.location,
            "received_at": time.time(),
        })
        # battery/voltage 퍼블리셔가 없는 구성(ADC 노드 단독)에서는 이 토픽이
        # 유일한 전압원이므로 SAF-005 경로를 그대로 태운다.
        if not self._voltage_topic_seen:
            self._apply_voltage(voltage)

    def _tick_power(self) -> None:
        power = self._svc.power
        power.tick()
        status = power.status()
        self._svc.state.set_power(status)

        if status.mode.value != self._published_power_mode:
            self._published_power_mode = status.mode.value
            self.power_mode_pub.publish(String(data=status.mode.value.lower()))

        now = time.monotonic()
        if status.info_visible:
            if not self._info_was_visible or (now - self._info_last_pub) >= _INFO_REPUBLISH_S:
                self._publish_display_info(status)
                self._info_last_pub = now
            if not self._info_was_visible:
                self._set_led_gauge(self._svc.state.snapshot().battery.percent)
        elif self._info_was_visible:
            self._clear_led()
        self._info_was_visible = status.info_visible

    def _publish_display_info(self, status) -> None:
        snapshot = self._svc.state.snapshot()
        payload = {
            "battery_percent": round(snapshot.battery.percent, 1),
            "battery_voltage": (round(snapshot.battery.voltage, 2)
                                if snapshot.battery.voltage is not None else None),
            "robot_id": snapshot.robot_id,
            "mode": snapshot.mode.value,
            "navigation": snapshot.navigation.value,
            "health": self.diagnostics.summary_health().value,
            "estop": snapshot.safety.estop,
            "address": self._api_endpoint(),
            "reason": status.last_wake_reason,
            "presence": status.presence.value,
            "hold_s": round(self._svc.power.info_hold_s, 1),
        }
        self.display_info_pub.publish(String(data=json.dumps(payload)))

    def _api_endpoint(self) -> str:
        """정보 화면에 띄울 접속 주소. 실패해도 화면을 막지 않는다."""
        if self._api_address is not None:
            return self._api_address
        port = self._svc.config.get("network", {}).get("api_port", 8080)
        host = socket.gethostname()
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("8.8.8.8", 80))       # 패킷은 나가지 않는다 — 경로 조회용
            host = probe.getsockname()[0]
        except OSError:
            pass
        finally:
            probe.close()
        self._api_address = f"http://{host}:{port}"
        return self._api_address

    def _set_led_gauge(self, percent: float) -> None:
        for floor, r, g, b in _LED_STEPS:
            if percent >= floor:
                self._call_led("fill", r, g, b)
                return

    def _clear_led(self) -> None:
        self._call_led("clear", 0, 0, 0)

    def _call_led(self, command: str, r: int, g: int, b: int) -> None:
        """LED는 부가 표시다 — 서비스가 없으면 조용히 건너뛴다."""
        if not self._led_client.service_is_ready():
            return
        request = SetLed.Request()
        request.command = command
        request.pixels = []
        request.r, request.g, request.b = r, g, b
        self._led_client.call_async(request)

    def _setup_diagnostics(self) -> None:
        self.diagnostics = DiagnosticsCollector()
        self.diagnostics.register("rosy_core", lambda: HealthState.OK)
        self.diagnostics.register("cpu", CpuLoadProvider())
        self.diagnostics.register("memory", MemoryAvailableProvider())
        self.diagnostics.register("disk", disk_provider("/"))
        self.diagnostics.register("odom_topic", topic_freshness_provider(
            lambda: self._last_odom_ts, stale_s=2.0))

    def _tick_diagnostics(self) -> None:
        results = self.diagnostics.collect()
        for component, health in results.items():
            self._svc.state.set_diagnostic(component, health)

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

    def save_map(self, name: str) -> str:
        """NAV-005: slam_toolbox SaveMap 호출 → map_id 발급 (D-13).

        파일을 찾으면 내용 체크섬, 못 찾으면 name+시각 해시로 대체 map_id.
        """
        if not self._slam_client.wait_for_service(timeout_sec=1.0):
            raise RuntimeError("slam_toolbox save_map service unavailable")
        request = SaveMap.Request()
        request.name = name
        future = self._slam_client.call_async(request)
        done = threading.Event()

        def _cb(_):
            done.set()

        future.add_done_callback(_cb)
        if not done.wait(timeout=15.0):
            raise RuntimeError("save_map service timeout")
        if future.result() is None or not getattr(future.result(), "result", True):
            raise RuntimeError("save_map service failed")

        digest_source = name
        for candidate in (Path(f"{name}.pgm"), Path(name)):
            if candidate.exists():
                digest_source = hashlib.sha1(candidate.read_bytes()).hexdigest()
                break
        else:
            digest_source = hashlib.sha1(
                f"{name}:{time.time()}".encode()).hexdigest()
        return f"{name}:{digest_source[:8]}"
