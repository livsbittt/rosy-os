#!/usr/bin/env python3
"""Publish semantic road evidence without ever publishing motion commands."""

import json
import time

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    QoSProfile,
    ReliabilityPolicy,
    qos_profile_sensor_data,
)
from sensor_msgs.msg import CompressedImage, Image
from std_msgs.msg import String

from .sensing.camera_homography import (
    CalibrationThresholds,
    load_homography_profile,
)
from .sensing.road import (
    RoadObservation,
    RoadPerceptionConfig,
    RoadPreviewConfig,
    PreviewRateLimiter,
    detect_road_observation,
    render_road_preview,
    road_observation_payload,
)


class RoadObserverNode(Node):
    def __init__(self):
        super().__init__('road_observer_node')
        self.declare_parameter('map_id', 'map_260905_update_v2')
        self.declare_parameter('scene_revision', 'road-scene-v1')
        self.declare_parameter('width', 320)
        self.declare_parameter('height', 240)
        self.declare_parameter('rotate_deg', 180)
        self.declare_parameter('camera_profile_revision', 'camera-profile-v1')
        self.declare_parameter('bright_threshold', 180)
        self.declare_parameter('lane_roi_top_fraction', 0.30)
        self.declare_parameter('horizontal_min_fraction', 0.40)
        self.declare_parameter('horizontal_padding_px', 2)
        self.declare_parameter('crosswalk_min_bars', 3)
        self.declare_parameter('crosswalk_max_gap_px', 20)
        self.declare_parameter('signal_roi_bottom_fraction', 0.35)
        self.declare_parameter('signal_min_pixels', 50)
        self.declare_parameter('dashboard_preview_fps', 2.0)
        self.declare_parameter('dashboard_preview_max_width', 640)
        self.declare_parameter('dashboard_preview_jpeg_quality', 72)
        self.declare_parameter('dashboard_preview_max_bytes', 512000)
        self.declare_parameter('dashboard_source', 'PINKY')
        self.declare_parameter('require_camera_controls_stable', True)
        self.declare_parameter('camera_homography_path', '')
        self.declare_parameter('camera_homography_enabled', False)
        self.declare_parameter('camera_homography_allow_uniform_resize', False)
        self.declare_parameter('camera_homography_max_fit_rmse_cm', 0.8)
        self.declare_parameter('camera_homography_max_validation_rmse_cm', 1.0)
        self.declare_parameter(
            'camera_homography_max_validation_error_cm', 2.0)
        self.declare_parameter('camera_homography_min_validation_points', 8)
        self.declare_parameter('camera_homography_min_validation_frames', 2)
        self.declare_parameter(
            'camera_homography_min_validation_span_cm', 10.0)
        self.declare_parameter('camera_homography_max_range_m', 0.6)

        self._config = RoadPerceptionConfig(
            bright_threshold=int(self.get_parameter('bright_threshold').value),
            lane_roi_top_fraction=float(
                self.get_parameter('lane_roi_top_fraction').value),
            horizontal_min_fraction=float(
                self.get_parameter('horizontal_min_fraction').value),
            horizontal_padding_px=int(
                self.get_parameter('horizontal_padding_px').value),
            crosswalk_min_bars=int(
                self.get_parameter('crosswalk_min_bars').value),
            crosswalk_max_gap_px=int(
                self.get_parameter('crosswalk_max_gap_px').value),
            signal_roi_bottom_fraction=float(
                self.get_parameter('signal_roi_bottom_fraction').value),
            signal_min_pixels=int(
                self.get_parameter('signal_min_pixels').value),
        )
        self._preview_config = RoadPreviewConfig(
            fps=float(self.get_parameter('dashboard_preview_fps').value),
            max_width=int(self.get_parameter(
                'dashboard_preview_max_width').value),
            jpeg_quality=int(self.get_parameter(
                'dashboard_preview_jpeg_quality').value),
            max_bytes=int(self.get_parameter(
                'dashboard_preview_max_bytes').value),
            source=str(self.get_parameter('dashboard_source').value),
        )
        self._preview_rate = PreviewRateLimiter(
            fps=self._preview_config.fps)
        self._homography = load_homography_profile(
            str(self.get_parameter('camera_homography_path').value),
            runtime_image_size=(int(self.get_parameter('width').value),
                                int(self.get_parameter('height').value)),
            runtime_rotate_deg=int(self.get_parameter('rotate_deg').value),
            runtime_profile_revision=str(
                self.get_parameter('camera_profile_revision').value),
            thresholds=CalibrationThresholds(
                max_fit_rmse_cm=float(self.get_parameter(
                    'camera_homography_max_fit_rmse_cm').value),
                max_validation_rmse_cm=float(self.get_parameter(
                    'camera_homography_max_validation_rmse_cm').value),
                max_validation_error_cm=float(self.get_parameter(
                    'camera_homography_max_validation_error_cm').value),
                min_validation_points=int(self.get_parameter(
                    'camera_homography_min_validation_points').value),
                min_validation_frames=int(self.get_parameter(
                    'camera_homography_min_validation_frames').value),
                min_validation_span_cm=float(self.get_parameter(
                    'camera_homography_min_validation_span_cm').value),
                max_range_m=float(self.get_parameter(
                    'camera_homography_max_range_m').value),
            ),
            allow_uniform_resize=bool(self.get_parameter(
                'camera_homography_allow_uniform_resize').value),
        )
        self._homography_enabled = bool(
            self.get_parameter('camera_homography_enabled').value)
        self._camera_controls_stable = False
        self.observation_pub = self.create_publisher(
            String, 'road/observation', 10)
        preview_qos = QoSProfile(
            depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.preview_pub = self.create_publisher(
            CompressedImage, 'camera/preview/compressed', preview_qos)
        self.create_subscription(
            Image, 'camera/front', self._on_camera, qos_profile_sensor_data)
        latched = QoSProfile(
            depth=1, reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(
            String, 'camera/controls', self._on_camera_controls, latched)
        self.create_subscription(
            String, 'camera/calibration/cmd', self._on_calibration_command, 10)

    def _stamp(self, msg: Image) -> float:
        return (
            float(msg.header.stamp.sec)
            + float(msg.header.stamp.nanosec) * 1e-9
        )

    def _ground(self):
        if self._homography_enabled and self._homography.eligible:
            return self._homography.model
        return None

    def _publish(self, stamp: float, observation: RoadObservation) -> None:
        payload = road_observation_payload(
            'CAMERA_ROAD', stamp,
            str(self.get_parameter('map_id').value),
            str(self.get_parameter('scene_revision').value),
            observation,
        )
        encoded = json.dumps(payload, sort_keys=True)
        self.observation_pub.publish(String(data=encoded))

    def _on_camera(self, msg: Image) -> None:
        observation = RoadObservation(None, None, None, None, False)
        frame = None
        try:
            if msg.encoding not in ('bgr8', 'rgb8'):
                raise ValueError(
                    f'unsupported camera encoding {msg.encoding!r}')
            pixels = np.frombuffer(msg.data, dtype=np.uint8)
            expected = int(msg.height) * int(msg.width) * 3
            if pixels.size != expected:
                raise ValueError(
                    'camera payload size does not match dimensions')
            frame = pixels.reshape((int(msg.height), int(msg.width), 3))
            if msg.encoding == 'rgb8':
                frame = frame[:, :, ::-1]
            if (self._camera_controls_stable or not bool(self.get_parameter(
                    'require_camera_controls_stable').value)):
                observation = detect_road_observation(
                    frame, ground=self._ground(), config=self._config)
        except ValueError as exc:
            self.get_logger().warning(
                f'invalid semantic road frame: {exc}')
        stamp = self._stamp(msg)
        self._publish(stamp, observation)
        if frame is not None:
            self._publish_preview(msg, frame, observation, stamp)

    def _publish_preview(self, msg: Image, frame: np.ndarray,
                         observation: RoadObservation, stamp: float) -> None:
        if not self._preview_rate.allow(time.monotonic()):
            return
        try:
            preview = render_road_preview(
                frame,
                observation,
                source=self._preview_config.source,
                max_width=self._preview_config.max_width,
            )
            ok, encoded = cv2.imencode('.jpg', preview, [
                cv2.IMWRITE_JPEG_QUALITY,
                self._preview_config.jpeg_quality,
            ])
        except (ValueError, cv2.error) as exc:
            self.get_logger().warning(
                f'camera preview render/encode failed: {exc}')
            return
        if not ok:
            self.get_logger().warning('camera preview JPEG encode failed')
            return
        if int(encoded.size) > self._preview_config.max_bytes:
            self.get_logger().warning(
                'camera preview exceeds configured byte budget')
            return
        output = CompressedImage()
        output.header = msg.header
        source = self._preview_config.source.upper()
        output.format = (
            f'jpeg; source={source}; width={preview.shape[1]}; '
            f'height={preview.shape[0]}; overlay=semantic-road-v1'
        )
        output.data = encoded.tobytes()
        self.preview_pub.publish(output)

    def _on_camera_controls(self, msg: String) -> None:
        summary = str(msg.data)
        self._camera_controls_stable = (
            summary.startswith('exposure=')
            or summary.startswith('v4l2 exposure=')
        )

    def _on_calibration_command(self, msg: String) -> None:
        command = str(msg.data).strip().lower()
        if command not in ('enable', 'disable'):
            return
        self._homography_enabled = command == 'enable'
        if self._homography_enabled and not self._homography.eligible:
            self.get_logger().warning(
                'road range remains disabled: validation_failed')


def main():
    rclpy.init()
    node = RoadObserverNode()
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
