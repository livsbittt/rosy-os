"""core.bridge.translate — ROS 메시지를 도메인 dict 로 옮기는 순수 변환.

`ros_bridge` 는 rclpy 없이는 import 조차 되지 않는다. 그래서 브리지 안에 있던
변환 코드는 Windows·CI 어디서도 실행되지 못했고, 검증은 "소스에 이 문자열이
있는가"를 확인하는 수준에 머물렀다 — 값이 틀려도 통과하는 테스트다.

이 모듈은 ROS 타입을 import 하지 않는다. 필요한 속성만 읽는 duck typing 이라
평범한 객체로 호출할 수 있고, 그래서 실제로 테스트된다. 여기 있는 함수는
전부 부작용이 없다: 상태를 만지는 일은 브리지가 한다.
"""

from __future__ import annotations

import math
from typing import Any, Optional


def yaw_from_quat(q: Any) -> float:
    """쿼터니언의 z 축 회전. 브리지 세 곳에 같은 식이 흩어져 있던 것을 모았다."""
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y ** 2 + q.z ** 2))


def _origin(pose: Any) -> dict[str, float]:
    return {
        "x": float(pose.position.x),
        "y": float(pose.position.y),
        "yaw": yaw_from_quat(pose.orientation),
    }


def grid_from_occupancy(msg: Any) -> dict[str, Any]:
    """`nav_msgs/OccupancyGrid` → MAP-003 스냅샷 격자."""
    info = msg.info
    return {
        "width": int(info.width),
        "height": int(info.height),
        "resolution": float(info.resolution),
        "origin": _origin(info.origin),
        "data": list(msg.data),
    }


def grid_from_costmap(msg: Any) -> dict[str, Any]:
    """`nav2_msgs/Costmap` → 같은 격자 형태. 메타데이터 필드 이름만 다르다."""
    meta = msg.metadata
    return {
        "width": int(meta.size_x),
        "height": int(meta.size_y),
        "resolution": float(meta.resolution),
        "origin": _origin(meta.origin),
        "data": list(msg.data),
    }


def path_points(msg: Any) -> list[dict[str, float]]:
    """`nav_msgs/Path` → x/y 목록. 고도와 자세는 스냅샷이 쓰지 않는다."""
    return [
        {"x": float(ps.pose.position.x), "y": float(ps.pose.position.y)}
        for ps in msg.poses
    ]


def odom_sample(msg: Any) -> dict[str, float]:
    """`nav_msgs/Odometry` → 포즈와 속도."""
    pose = msg.pose.pose
    twist = msg.twist.twist
    return {
        "x": float(pose.position.x),
        "y": float(pose.position.y),
        "yaw": yaw_from_quat(pose.orientation),
        "linear_x": float(twist.linear.x),
        "angular_z": float(twist.angular.z),
    }


def lidar_sample(msg: Any, received_at: float) -> dict[str, Any]:
    return {
        "frame_id": msg.header.frame_id,
        "range_min": msg.range_min,
        "range_max": msg.range_max,
        "angle_min": msg.angle_min,
        "angle_max": msg.angle_max,
        "num_ranges": len(msg.ranges),
        "ranges": list(msg.ranges),
        "received_at": received_at,
    }


def imu_sample(msg: Any, received_at: float) -> dict[str, Any]:
    return {
        "orientation_yaw": yaw_from_quat(msg.orientation),
        "angular_velocity_z": msg.angular_velocity.z,
        "linear_accel_x": msg.linear_acceleration.x,
        "received_at": received_at,
    }


def ultrasonic_sample(msg: Any, received_at: float) -> dict[str, Any]:
    return {
        "frame_id": msg.header.frame_id,
        "range": float(msg.range),
        "min_range": msg.min_range,
        "max_range": msg.max_range,
        "field_of_view": msg.field_of_view,
        "received_at": received_at,
    }


def usable_range(sample: dict[str, Any]) -> Optional[float]:
    """센서가 스스로 보고한 유효 구간 안의 표본만 정책에 넣는다 (PWR-002).

    구간 밖 값은 "가까운 물체 없음"을 뜻하는 포화값이거나 노이즈다. 그것을
    거리로 읽으면 아무도 없는 복도에서 로봇이 깨어난다.
    """
    value = sample["range"]
    if not math.isfinite(value):
        return None
    if not (sample["min_range"] <= value <= sample["max_range"]):
        return None
    return value


def battery_sample(msg: Any, received_at: float) -> dict[str, Any]:
    return {
        "voltage": float(msg.voltage),
        "percentage": float(msg.percentage),
        "power_supply_status": int(msg.power_supply_status),
        "location": msg.location,
        "received_at": received_at,
    }
