"""Verify shipped parameter selectors with real ROS name resolution."""
from pathlib import Path
import unittest
import tempfile

try:
    import rclpy
except ImportError:
    rclpy = None

if rclpy is not None:
    from rclpy.node import Node
    import yaml
    from rosy_control.calibration_storage import merge_calibration


@unittest.skipIf(rclpy is None, 'Requires isolated ROS Jazzy graph')
class ParameterGraphTests(unittest.TestCase):
    def test_saved_legacy_calibration_is_consumed_by_namespaced_owner_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'calibration.yaml'
            path.write_text('safety_node:\n  ros__parameters:\n    imu_roll0: 0.25\n')
            merge_calibration(str(path), 'safety_node:\n  ros__parameters:\n    imu_pitch0: 0.5\n')
            rclpy.init(args=['--ros-args', '--params-file', str(path)])
            nodes = []
            try:
                for name in ('safety_node', 'unrelated_node'):
                    node = Node(name, namespace='rosy_01',
                                automatically_declare_parameters_from_overrides=True)
                    nodes.append(node)
                self.assertEqual(nodes[0].get_parameter('imu_roll0').value, 0.25)
                self.assertEqual(nodes[0].get_parameter('imu_pitch0').value, 0.5)
                self.assertFalse(nodes[1].has_parameter('imu_roll0'))
                self.assertFalse(nodes[1].has_parameter('imu_pitch0'))
            finally:
                for node in nodes:
                    node.destroy_node()
                rclpy.shutdown()

    def test_per_node_files_apply_under_root_and_robot_namespaces(self):
        config = Path(__file__).parents[1] / 'config'
        for path in sorted(config.glob('*.yaml')):
            document = yaml.safe_load(path.read_text(encoding='utf-8'))
            for selector, settings in document.items():
                if selector == '/**':
                    continue
                name = selector.rsplit('/', 1)[-1]
                for namespace in ('', 'rosy_01', 'rosy_02'):
                    rclpy.init(args=['--ros-args', '--params-file', str(path)])
                    node = None
                    try:
                        node = Node(name, namespace=namespace,
                                    automatically_declare_parameters_from_overrides=True)
                        for key, expected in settings['ros__parameters'].items():
                            self.assertTrue(node.has_parameter(key),
                                            (path.name, namespace, key))
                            actual = node.get_parameter(key).value
                            if isinstance(expected, list):
                                actual = list(actual)
                            self.assertEqual(actual, expected, (path.name, namespace, key))
                    finally:
                        if node is not None:
                            node.destroy_node()
                        rclpy.shutdown()


if __name__ == '__main__':
    unittest.main()
