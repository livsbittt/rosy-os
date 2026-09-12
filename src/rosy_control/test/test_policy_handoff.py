"""The sensor producer passes real observation clocks into CORE's policy."""
import unittest

from rosy_control.control.command_gate import CommandPolicy, GateInputs
from rosy_control.control.policy_handoff import ControlPolicyProducer
from rosy_control.sensing.observation import Observations


class ControlPolicyProducerTests(unittest.TestCase):
    def setUp(self):
        self.observations = Observations(max_age=.5)
        self.observations.add('lidar', 10.0, source=100.0, source_now=100.0)
        self.observations.add('imu', 10.0)
        self.policy = CommandPolicy('applied-profile-1')
        self.producer = ControlPolicyProducer(self.policy, self.observations,
                                              ('lidar', 'imu'), 'applied-profile-1')

    def test_publishes_gate_inputs_with_sensor_deadline_and_applied_revision(self):
        self.assertTrue(self.producer.publish(GateInputs(), now=10.01))
        result = self.policy.evaluate(.01, 0., 10.49)
        self.assertIsNotNone(result)
        snapshot, _ = result
        self.assertEqual(snapshot.sequence, 1)
        self.assertEqual(snapshot.observed_at, 10.0)
        self.assertEqual(snapshot.expires_at, 10.5)
        self.assertEqual(snapshot.calibration_revision, 'applied-profile-1')

    def test_required_stream_loss_invalidates_the_previous_snapshot(self):
        self.assertTrue(self.producer.publish(GateInputs(), now=10.01))
        self.observations.rows['imu'].valid = False
        self.assertFalse(self.producer.publish(GateInputs(), now=10.02))
        self.assertIsNone(self.policy.evaluate(.01, 0., 10.02))

    def test_replayed_or_wrong_applied_revision_cannot_publish(self):
        self.assertFalse(self.producer.publish(GateInputs(), now=10.01,
                                                applied_revision='requested-only'))
        self.assertIsNone(self.policy.evaluate(.01, 0., 10.02))
        self.assertEqual(self.producer.sequence, 1)

    def test_producer_does_not_refresh_receive_or_source_clocks(self):
        self.assertTrue(self.producer.publish(GateInputs(), now=10.01))
        self.assertFalse(self.producer.publish(GateInputs(), now=10.60))
        self.assertIsNone(self.policy.evaluate(.01, 0., 10.60))
        self.assertEqual(self.observations.generation('lidar'), 1)
