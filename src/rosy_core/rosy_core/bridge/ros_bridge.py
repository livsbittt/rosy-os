"""rosy_core.bridge.ros_bridge — ROS-101 모든 ROS I/O 집중 (P1-3).

- 유일한 cmd_vel 퍼블리셔 (D-2): 50 Hz select_output → publish
- 구독: odom / battery/voltage / nav_cmd_vel(Nav2 출력 리매핑 입력)
       / us_sensor/range, batt_state (PWR-002 근접 웨이크·배터리 표시)
       / map, plan, local/global costmap (MAP-003 스냅샷)
- 발행: power/mode, display/info (PWR-003) — LED는 set_led 서비스로 구동
- LiDAR 모터: start_motor / stop_motor 서비스로 STANDBY 듀티 조정 (PWR-005)
- Nav2 NavigateToPose 액션 클라이언트 (NavExecutor 구현)
- TF: map → base pose 조회 (frame_prefix 반영, §6.1)
"""

from __future__ import annotations

import json
import math
import hashlib
import threading
import time
from pathlib import Path
from typing import Optional

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from nav_msgs.msg import OccupancyGrid, Odometry, Path
from nav2_msgs.action import NavigateToPose
from nav2_msgs.msg import Costmap
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import BatteryState, Imu, LaserScan, Range
from std_msgs.msg import Bool, Float32, String
from std_srvs.srv import Empty

from rosy_core.bridge import display, translate
from rosy_core.bridge.goal_tracker import GoalTracker
from rosy_core.maps import occupancy_map_id
from rosy_core.navigation.initial_pose import amcl_pose_covariance
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
from rosy_core.navigation.manager import NavGoalSpec, NavigationError
from rosy_core.power.battery import BatteryLevel, resolve_led
from rosy_core.protocol.schemas import HealthState

# 늦게 뜬 노드도 현재 모드를 즉시 받도록 latch 한다 (PWR-003).
_LATCHED = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                      durability=DurabilityPolicy.TRANSIENT_LOCAL)


# 정보 창이 열려 있는 동안 display/info 재발행 간격 (s).
_INFO_REPUBLISH_S = 1.0



class RosBridge:
    def __init__(self, node: Node, services) -> None:
        self._node = node
        self._svc = services
        cfg = services.config
        self._frame_prefix = str(cfg.get("robot", {}).get("frame_prefix", ""))
        self._base_frame = f"{self._frame_prefix}base_footprint"
        self._map_frame = "map"
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
        node.create_subscription(OccupancyGrid, "map", self._on_map, _LATCHED)
        node.create_subscription(Path, "plan", self._on_plan, 10)
        node.create_subscription(Costmap, "local_costmap/costmap", self._on_local_costmap, 10)
        node.create_subscription(Costmap, "local_costmap/costmap_raw", self._on_local_costmap, 10)
        node.create_subscription(Costmap, "global_costmap/costmap", self._on_global_costmap, 10)
        node.create_subscription(Costmap, "global_costmap/costmap_raw", self._on_global_costmap, 10)

        self.power_mode_pub = node.create_publisher(String, "power/mode", _LATCHED)
        self.display_info_pub = node.create_publisher(String, "display/info", 10)
        self.dock_exemption_pub = node.create_publisher(
            Bool, "docking/collision_exemption", _LATCHED)
        self._led_client = node.create_client(SetLed, "set_led")
        # sllidar_ros2가 제공하는 모터 제어 서비스 (PWR-005).
        self._lidar_start_client = node.create_client(Empty, "start_motor")
        self._lidar_stop_client = node.create_client(Empty, "stop_motor")

        self._cmd_timer = node.create_timer(1.0 / 50.0, self._publish_cmd_vel)
        self._state_timer = node.create_timer(1.0 / self._state_hz, self._tick_state)
        self._diag_timer = node.create_timer(1.0, self._tick_diagnostics)
        self._power_timer = node.create_timer(1.0 / 5.0, self._tick_power)
        self._dock_timer = node.create_timer(1.0 / 5.0, self._tick_docking)
        self._swarm_timer = node.create_timer(1.0 / 5.0, self._tick_swarm)
        self._goals = GoalTracker()

        self._last_odom_ts = 0.0
        self._last_odom_xy = None
        self._dock_odom_mark = None
        self._applied_dock_exemption = False
        # slam_toolbox 를 모듈 최상단에서 임포트하면 브리지 임포트가, 따라서
        # 노드 기동 전체가 실패한다. core 이미지에는 설치되지 않고 pi5-lite
        # capabilities 도 slam: false 다. 여기서 시도하고 부재는 기록만 해서
        # SLAM 을 실제로 쓰는 경로에서만 드러나게 한다. 클라이언트를 생성자에서
        # 만들어야 DDS 엔드포인트 매칭에 노드 수명만큼의 시간이 주어진다.
        self._slam_client = None
        try:
            from slam_toolbox.srv import SaveMap
        except ImportError as exc:
            node.get_logger().warning(
                f"slam_toolbox unavailable; map saving disabled ({exc})")
        else:
            self._slam_client = node.create_client(SaveMap, "slam_toolbox/save_map")

        self._published_power_mode: Optional[str] = None
        # 드라이버는 core보다 먼저 떠서 이미 회전 중이다 — 기동 시 불필요한 호출 방지.
        self._applied_lidar_spinning = True
        self._info_was_visible = False
        self._applied_led = None
        self._info_last_pub = 0.0
        self._voltage_topic_seen = False
        self._api_address: Optional[str] = None

        self._setup_diagnostics()
        self._svc.nav.executor = self
        self._svc.docking.executor = self
        self._node.get_logger().info("ros_bridge ready (cmd_vel sole publisher @50Hz)")

    def _on_odom(self, msg: Odometry) -> None:
        self._last_odom_ts = time.monotonic()
        sample = translate.odom_sample(msg)
        self._svc.state.set_pose(sample["x"], sample["y"], sample["yaw"])
        self._svc.state.set_velocity(sample["linear_x"], sample["angular_z"])
        self._last_odom_xy = (sample["x"], sample["y"])
        self._svc.nav.on_pose_progress(sample["x"], sample["y"])

    def _on_battery(self, msg: Float32) -> None:
        self._voltage_topic_seen = True
        self._apply_voltage(float(msg.data))

    def _apply_voltage(self, voltage: float) -> None:
        """생 표본을 정책 계층에 넣고, 그것이 거른 값으로만 SAF-005를 태운다.

        예전에는 표본 하나가 곧장 임계 판정을 거쳐 E-Stop 까지 갔다. 모터가
        기동할 때의 전압 새그 한 발이 크리티컬 정책을 오발화시키던 경로다.
        """
        if not math.isfinite(voltage):
            return

        battery = self._svc.battery
        battery.on_voltage(voltage)

        percent = battery.percent
        if percent is None:
            return

        self._svc.state.set_battery(percent, voltage)
        self._svc.state.set_battery_status(battery.status())
        self._svc.power.on_battery_alert(battery.level.value)

        # DEEP 은 유예 전에 먼저 움직임을 멈춘다. 모터가 최대 소모원이고, 부하가
        # 빠져야 전압이 휴지 곡선 쪽으로 회복해 셧다운 판단의 근거가 나아진다.
        if battery.level is BatteryLevel.DEEP:
            self._svc.safety.trigger_estop("battery_deep")

        # 20% 경고에서 도크 복귀를 시도한다 (DNC-006). 도크가 없거나
        # 미지원이면 아무 일도 하지 않고 SAF-005 폴백이 그대로 남는다.
        self._svc.docking.on_battery_level(battery.level)

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

    def _on_map(self, msg: OccupancyGrid) -> None:
        try:
            grid = translate.grid_from_occupancy(msg)
            self._svc.maps.set_map(grid)
            current = self._svc.state.map_id
            if current is None or str(current).startswith("occupancy:"):
                self._svc.state.set_map_id(occupancy_map_id(grid))
        except ValueError as exc:
            self._node.get_logger().warning(f"ignored occupancy map: {exc}")

    def _on_plan(self, msg: Path) -> None:
        try:
            self._svc.maps.set_path(translate.path_points(msg))
        except ValueError as exc:
            self._node.get_logger().warning(f"ignored nav path: {exc}")

    def _on_local_costmap(self, msg: Costmap) -> None:
        try:
            self._svc.maps.set_costmap("local", translate.grid_from_costmap(msg))
        except ValueError as exc:
            self._node.get_logger().warning(f"ignored local costmap: {exc}")

    def _on_global_costmap(self, msg: Costmap) -> None:
        try:
            self._svc.maps.set_costmap("global", translate.grid_from_costmap(msg))
        except ValueError as exc:
            self._node.get_logger().warning(f"ignored global costmap: {exc}")

    def _on_scan(self, msg: LaserScan) -> None:
        self._svc.state.set_sensor("lidar", translate.lidar_sample(msg, time.time()))

    def _on_imu(self, msg: Imu) -> None:
        self._svc.state.set_sensor("imu", translate.imu_sample(msg, time.time()))

    # --- PWR-002~004 근접 웨이크 --------------------------------------------

    def _on_us_range(self, msg: Range) -> None:
        sample = translate.ultrasonic_sample(msg, time.time())
        self._svc.state.set_sensor("ultrasonic", sample)
        usable = translate.usable_range(sample)
        if usable is not None:
            self._svc.power.on_range(usable)

    def _on_batt_state(self, msg: BatteryState) -> None:
        sample = translate.battery_sample(msg, time.time())
        self._svc.state.set_sensor("battery", sample)
        voltage = sample["voltage"]
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

        self._reconcile_lidar(status.lidar_spinning)

        now = time.monotonic()
        if status.info_visible:
            if not self._info_was_visible or (now - self._info_last_pub) >= _INFO_REPUBLISH_S:
                self._publish_display_info(status)
                self._info_last_pub = now
        self._info_was_visible = status.info_visible

        self._reconcile_led(status.info_visible, now)

    def _publish_display_info(self, status) -> None:
        payload = display.info_payload(
            self._svc.state.snapshot(), status,
            health=self.diagnostics.summary_health().value,
            address=self._api_endpoint(),
            hold_s=self._svc.power.info_hold_s,
        )
        self.display_info_pub.publish(String(data=json.dumps(payload)))

    def _api_endpoint(self) -> str:
        """정보 화면에 띄울 접속 주소. 한 번 풀고 캐시한다."""
        if self._api_address is None:
            port = self._svc.config.get("network", {}).get("api_port", 8080)
            self._api_address = display.resolve_api_address(port)
        return self._api_address

    def _reconcile_led(self, info_visible: bool, now: float) -> None:
        """중재 결과에 LED 를 맞춘다 (SAF-005 경보 > 정보창 게이지).

        명령이 바뀔 때만 서비스를 부른다. 이 틱은 5 Hz 이고 DEEP 경보는 2 Hz 로
        깜빡이므로, 그러지 않으면 같은 색을 초당 다섯 번 다시 칠하게 된다.
        """
        command = resolve_led(
            self._svc.battery.led_alert,
            info_visible=info_visible,
            gauge_percent=self._svc.state.snapshot().battery.percent,
            now=now,
        )
        if command == self._applied_led:
            return
        self._call_led(command.command, command.r, command.g, command.b)
        self._applied_led = command

    def _reconcile_lidar(self, spinning: bool) -> None:
        """PowerManager가 선언한 회전 의도에 LiDAR 모터를 맞춘다 (PWR-005).

        LED와 달리 조용히 포기하지 않는다. LiDAR는 내비게이션 입력이므로 서비스가
        아직 준비되지 않았으면 latch 없이 다음 틱(5 Hz)에 재시도한다. 그래야
        드라이버가 늦게 떠도 정지 상태로 방치되지 않는다.
        """
        if spinning == self._applied_lidar_spinning:
            return
        client = self._lidar_start_client if spinning else self._lidar_stop_client
        if not client.service_is_ready():
            return
        client.call_async(Empty.Request())
        self._applied_lidar_spinning = spinning
        self._node.get_logger().info(
            "lidar motor %s requested by power policy" % ("start" if spinning else "stop"))

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


    # --- DockingExecutor 구현 (docking.manager와 계약) -------------------------
    #
    # 정책은 rosy_core.docking.manager 가 갖고 여기는 조정만 한다 — power/mode 와
    # PWR-005 LiDAR 의도와 같은 형태다.

    def navigate_to(self, pose) -> None:
        """스테이징 주행. 도킹 액션이 Nav2 구간까지 소유하므로 여기서 부른다."""
        self.send_goal(NavGoalSpec(x=pose.x, y=pose.y, yaw=pose.yaw))

    def cancel_navigation(self) -> None:
        self.cancel_goal()

    def drive(self, linear: float, angular: float) -> None:
        """접근·후진 속도. 기존 cmd_vel 멀렉서를 통과시킨다.

        nav 슬롯을 쓴다. 수동 조작(우선순위 3)이 도킹(4)을 이겨야 하는데 멀렉서가
        이미 manual 을 위에 두고 있고, DOCKING 과 NAVIGATION 사이의 구분은 여기서
        의미가 없다 — 도킹 중에는 도킹 매니저가 주행을 소유하므로 경쟁할 nav
        목표 자체가 존재하지 않는다.
        """
        self._svc.command.set_nav_twist(CoreTwist(linear=linear, angular=angular))

    def stop(self) -> None:
        self._svc.command.set_nav_twist(CoreTwist(linear=0.0, angular=0.0))

    def set_collision_exemption(self, enabled: bool) -> None:
        """도크는 코스트맵에 장애물로 찍힌다 — 접근 구간에만 면제를 선언한다.

        Nav2 에 이를 끄는 표준 서비스가 없어서 의도를 토픽으로 내보낸다. 실제
        코스트맵 연동은 실기 항목으로 남는다(DOCK_GO).
        """
        if enabled == self._applied_dock_exemption:
            return
        self._applied_dock_exemption = enabled
        self.dock_exemption_pub.publish(Bool(data=bool(enabled)))
        self._node.get_logger().info(
            "docking collision exemption %s" % ("on" if enabled else "off"))

    def reset_odometry_mark(self) -> None:
        self._dock_odom_mark = self._last_odom_xy

    def travelled_m(self) -> float:
        """마크 이후 이동 거리. 언도킹은 센서를 보지 않고 이 값만 쓴다."""
        if self._dock_odom_mark is None or self._last_odom_xy is None:
            return 0.0
        return math.hypot(self._last_odom_xy[0] - self._dock_odom_mark[0],
                          self._last_odom_xy[1] - self._dock_odom_mark[1])

    def _tick_swarm(self) -> None:
        """SWM-004 는 마감시각으로 판정한다 — 스트림이 끊기면 아무 프레임도
        오지 않으므로 소켓 쪽에서는 알아챌 수 없다."""
        try:
            self._svc.swarm.tick()
        except Exception as exc:  # 추종 실패가 브리지 루프를 멈추면 안 된다
            self._node.get_logger().warning(f"swarm tick failed: {exc}")

    def _tick_docking(self) -> None:
        docking = self._svc.docking
        docking.on_navigation_state(self._svc.nav.nav_state)
        docking.set_manual_active(self._svc.command.manual_active)
        docking.tick()
        self._svc.state.set_docking(docking.status())

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
        generation = self._goals.opening()
        future = self.nav_client.send_goal_async(goal)
        future.add_done_callback(
            lambda done, gen=generation: self._goal_response_cb(done, gen))

    def _goal_response_cb(self, future, generation: int) -> None:
        goal_handle = future.result()
        if goal_handle is None or not goal_handle.accepted:
            if self._goals.rejected(generation):
                self._svc.nav.on_result(False, "REJECTED")
            return
        if not self._goals.accepted(generation, goal_handle):
            # 이미 지나간 목표의 수락이다(선점됐거나, 보내는 사이 취소됐다).
            # 살려두면 아무도 거두지 않는 Nav2 목표가 남는다.
            goal_handle.cancel_goal_async()
            return
        self._svc.nav.on_goal_accepted()
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(
            lambda done, gen=generation: self._result_cb(done, gen))

    def _result_cb(self, future, generation: int) -> None:
        if not self._goals.finished(generation):
            # 선점된 목표의 뒤늦은 결과. moving goal 에서는 abort 로 끝나며,
            # 이것을 현재 목표의 실패로 읽으면 nav_state 가 FAILED 로 떨어져
            # 이어지는 HOLD 의 취소가 통째로 무시된다.
            return
        try:
            result = future.result()
            self._svc.nav.on_result(result.status == 4)
        except Exception as exc:
            self._svc.nav.on_result(False, str(exc))

    def cancel_goal(self) -> None:
        handles = self._goals.cancel_all()
        for handle in handles:
            handle.cancel_goal_async()
        if handles:
            self._node.get_logger().info(
                f"navigation cancel requested ({len(handles)} goal(s))")

    def send_initial_pose(self, x: float, y: float, yaw: float) -> None:
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = self._map_frame
        msg.header.stamp = self._node.get_clock().now().to_msg()
        msg.pose.pose.position.x = x
        msg.pose.pose.position.y = y
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        msg.pose.covariance = amcl_pose_covariance()
        self.initialpose_pub.publish(msg)

    def save_map(self, name: str) -> str:
        """NAV-005: slam_toolbox SaveMap 호출 → map_id 발급 (D-13).

        파일을 찾으면 내용 체크섬, 못 찾으면 name+시각 해시로 대체 map_id.
        """
        if self._slam_client is None:
            raise RuntimeError(
                "slam_toolbox is not installed in this runtime; map saving is unavailable")
        if not self._slam_client.wait_for_service(timeout_sec=1.0):
            raise RuntimeError("slam_toolbox save_map service unavailable")
        request = self._slam_client.srv_type.Request()
        # SaveMap.srv 의 name 은 string 이 아니라 std_msgs/String 이다.
        request.name = String(data=name)
        future = self._slam_client.call_async(request)
        done = threading.Event()

        def _cb(_):
            done.set()

        future.add_done_callback(_cb)
        if not done.wait(timeout=15.0):
            raise RuntimeError("save_map service timeout")
        response = future.result()
        if response is None:
            raise RuntimeError("save_map service failed")
        # slam_toolbox 는 RESULT_SUCCESS=0, 실패가 1/255 다. 참/거짓으로 보면
        # 성공을 실패로, 실패를 성공으로 뒤집게 된다.
        code = response.result
        if code != 0:
            raise RuntimeError(f"save_map service failed (result={code})")

        digest_source = name
        for candidate in (Path(f"{name}.pgm"), Path(name)):
            if candidate.exists():
                digest_source = hashlib.sha1(candidate.read_bytes()).hexdigest()
                break
        else:
            digest_source = hashlib.sha1(
                f"{name}:{time.time()}".encode()).hexdigest()
        return f"{name}:{digest_source[:8]}"

    def reset_mapping(self) -> None:
        """NAV-005 세션 초기화 — 아직 실기가 없다.

        `hasattr` 뒤에 숨어 있던 자리다. 없는 메서드를 조용히 건너뛰면
        `POST /api/v1/slam/reset` 이 아무 일도 하지 않고 200 을 돌려준다.
        선언해 두고 명확한 코드로 실패하는 편이 CAP-003 이 요구하는 것이다
        (일반 실패가 아니라 `CAPABILITY_NOT_SUPPORTED`).

        실물은 slam_toolbox `Reset` 서비스이며 `mapping/` 트리거에 걸려 있다
        — 이식원은 `rosy_navigation/scripts/nav2_web_server.py`.
        """
        raise NavigationError(
            "CAPABILITY_NOT_SUPPORTED",
            "slam_toolbox reset is not implemented in this runtime")
