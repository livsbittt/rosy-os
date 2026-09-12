"""Actual CORE publish method and DDS output in a network-isolated ROS test."""
import ast
from pathlib import Path
from types import SimpleNamespace
import time
import unittest
from unittest.mock import Mock

try:
    import rclpy
except ImportError:
    rclpy = None

if rclpy is not None:
    from rclpy.node import Node
    from geometry_msgs.msg import Twist
    from rosy_core.command.arbitration import Mode, ModeMachine, SourceRegistry
    from rosy_core.command.manager import CommandManager, Twist as CoreTwist
    from rosy_core.safety.manager import SafetyManager, SpeedLimits, BatteryPolicy, SafetyDecision


@unittest.skipIf(rclpy is None, 'Requires network-isolated ROS Jazzy')
class OutputGraphTests(unittest.TestCase):
    def test_invalid_worker_command_is_published_as_zero(self):
        self.exercise(float('nan'), False, None, (0., 0.))

    def test_required_missing_policy_publishes_zero(self):
        self.exercise(.1, True, None, (0., 0.))

    def test_policy_limit_reaches_actual_publisher(self):
        def limit(request):
            return SafetyDecision(request.command_id, request.source, request.calibration_revision,
                                  request.now, request.now + .1, .04, .06, 'limit')
        self.exercise(.1, True, limit, (.04, .06))

    def test_control_obstacle_gate_reaches_motor_topic(self):
        self.exercise(.1, True, None, (0., 0.), control_obstacle=True)

    def test_control_allows_explicit_reverse_past_front_obstacle(self):
        self.exercise(-.1, True, None, (-.1, .1), control_obstacle=True)

    def exercise(self, linear, required, provider, expected, control_obstacle=False):
        path = Path(__file__).parents[1] / 'rosy_core/bridge/ros_bridge.py'
        cls = next(n for n in ast.parse(path.read_text(encoding='utf-8')).body
                   if isinstance(n, ast.ClassDef) and n.name == 'RosBridge')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_publish_cmd_vel')
        scope = dict(Twist=Twist)
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), scope)
        modes = ModeMachine()
        modes.transition(Mode.NAVIGATION)
        safety = SafetyManager(SpeedLimits(), BatteryPolicy(), policy_required=required)
        if provider is not None:
            safety.bind_policy(provider, 'calibration-1')
        command = CommandManager(SourceRegistry(), modes, safety)
        rclpy.init()
        node = Node('output_probe', namespace='rosy_01')
        observed = []
        node.create_subscription(Twist, 'cmd_vel', lambda msg: observed.append(msg), 10)
        bridge = SimpleNamespace(_svc=SimpleNamespace(command=command, power=Mock()),
                                 cmd_vel_pub=node.create_publisher(Twist, 'cmd_vel', 10))
        try:
            if control_obstacle:
                from rosy_control.control.command_gate import CommandPolicy, GateInputs, GateSnapshot
                policy = CommandPolicy('applied-revision')
                safety.bind_control_policy(policy)
                now = time.monotonic()
                self.assertTrue(policy.update(GateSnapshot(policy.session, 1, policy.revision,
                    now, now + .5, GateInputs(obstacle=True))))
            command.set_nav_twist(CoreTwist(linear, .1))
            deadline = time.monotonic() + 5.
            while not observed and time.monotonic() < deadline:
                scope['_publish_cmd_vel'](bridge)
                rclpy.spin_once(node, timeout_sec=.05)
            self.assertTrue(observed)
            self.assertEqual((observed[-1].linear.x, observed[-1].angular.z), expected)
            if control_obstacle:
                self.assertFalse(safety.estop)
            if expected == (0., 0.):
                bridge._svc.power.on_activity.assert_not_called()
        finally:
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    unittest.main()
