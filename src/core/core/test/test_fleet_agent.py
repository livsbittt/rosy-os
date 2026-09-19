"""Fleet outbound agent stays local-first. There is no fleet server in this repo."""

from core_features.fleet_agent.agent import FleetAgent


def test_fleet_agent_does_not_connect_or_enable():
    agent = FleetAgent()
    agent.start()
    assert agent.enabled is False
    assert agent.connected is False


def test_fleet_agent_start_does_not_open_a_url():
    seen = []

    class QuietAgent(FleetAgent):
        def _connect(self, url: str) -> None:
            seen.append(url)

    agent = QuietAgent()
    agent.start()
    assert seen == []
    assert agent.connected is False


def test_connect_raises_until_a_later_plan_enables_outbound():
    agent = FleetAgent()
    try:
        agent._connect("wss://fleet.example/ws/robots")
    except RuntimeError as exc:
        assert "not enabled" in str(exc)
    else:
        raise AssertionError("outbound must stay disabled in this slice")
