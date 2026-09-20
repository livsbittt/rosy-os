#!/usr/bin/env python3
"""Publish normalized white-line evidence from IR reflectance or camera frames.

This node owns no motion output. CORE chooses exactly one source and remains
the sole final ``cmd_vel`` publisher (D-143).
"""

import json

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import String, UInt16MultiArray

from .sensing.lane import (
    IRLineCalibration,
    detect_ir_line,
    detect_lane_error,
    line_observation_payload,
)


class LineObserverNode(Node):
    def __init__(self):
        super().__init__('line_observer_node')
        self.declare_parameter('ir_calibration_enabled', False)
        self.declare_parameter('ir_black', [0.0, 0.0, 0.0])
        self.declare_parameter('ir_white', [0.0, 0.0, 0.0])
        self.declare_parameter('ir_min_span', 100.0)
        self.declare_parameter('ir_min_white', 0.55)
        self.declare_parameter('ir_min_contrast', 0.15)
        self.declare_parameter('camera_bright_threshold', 180)
        self.declare_parameter('camera_roi_top_fraction', 0.4)
        self.declare_parameter('camera_washed_fraction', 0.4)
        self.declare_parameter('camera_min_pixels', 80)

        self._ir_calibration = None
        self._camera_controls_stable = False
        if bool(self.get_parameter('ir_calibration_enabled').value):
            self._ir_calibration = IRLineCalibration(
                black=tuple(self.get_parameter('ir_black').value),
                white=tuple(self.get_parameter('ir_white').value),
                min_span=float(self.get_parameter('ir_min_span').value),
            )

        self.observation_pub = self.create_publisher(String, 'line/observation', 10)
        self.create_subscription(
            UInt16MultiArray, 'ir_sensor/range', self._on_ir, qos_profile_sensor_data)
        self.create_subscription(
            Image, 'camera/front', self._on_camera, qos_profile_sensor_data)
        controls_qos = QoSProfile(
            depth=1, reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(
            String, 'camera/controls', self._on_camera_controls, controls_qos)
        if self._ir_calibration is None:
            self.get_logger().warning(
                'IR line calibration disabled; IR_LINE will remain fail-closed')

    def _stamp(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def _publish(self, source, observation, *, stamp=None) -> None:
        payload = line_observation_payload(
            source, self._stamp() if stamp is None else stamp, observation)
        self.observation_pub.publish(String(data=json.dumps(payload, sort_keys=True)))

    def _on_ir(self, msg: UInt16MultiArray) -> None:
        observation = None
        if self._ir_calibration is not None:
            try:
                observation = detect_ir_line(
                    list(msg.data), self._ir_calibration,
                    min_white=float(self.get_parameter('ir_min_white').value),
                    min_contrast=float(self.get_parameter('ir_min_contrast').value),
                )
            except ValueError as exc:
                self.get_logger().warning(f'invalid IR line sample: {exc}')
        self._publish('IR_LINE', observation)

    def _on_camera(self, msg: Image) -> None:
        observation = None
        if not self._camera_controls_stable:
            self._publish('CAMERA_LINE', None, stamp=(
                float(msg.header.stamp.sec) + float(msg.header.stamp.nanosec) * 1e-9))
            return
        try:
            channels = 1 if msg.encoding == 'mono8' else 3
            if msg.encoding not in ('mono8', 'bgr8', 'rgb8'):
                raise ValueError(f'unsupported camera encoding {msg.encoding!r}')
            expected = int(msg.height) * int(msg.width) * channels
            pixels = np.frombuffer(msg.data, dtype=np.uint8)
            if pixels.size != expected:
                raise ValueError('camera payload size does not match dimensions')
            frame = pixels.reshape((int(msg.height), int(msg.width), channels))
            if channels == 1:
                frame = frame[:, :, 0]
            elif msg.encoding == 'rgb8':
                frame = frame[:, :, ::-1]
            observation = detect_lane_error(
                frame,
                bright_threshold=int(self.get_parameter('camera_bright_threshold').value),
                roi_top_fraction=float(self.get_parameter('camera_roi_top_fraction').value),
                washed_fraction=float(self.get_parameter('camera_washed_fraction').value),
                min_pixels=int(self.get_parameter('camera_min_pixels').value),
            )
        except ValueError as exc:
            self.get_logger().warning(f'invalid camera line frame: {exc}')
        source_stamp = (float(msg.header.stamp.sec)
                        + float(msg.header.stamp.nanosec) * 1e-9)
        self._publish('CAMERA_LINE', observation, stamp=source_stamp)

    def _on_camera_controls(self, msg: String) -> None:
        summary = str(msg.data)
        self._camera_controls_stable = (
            summary.startswith('exposure=') or summary.startswith('v4l2 exposure='))


def main():
    rclpy.init()
    node = LineObserverNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
