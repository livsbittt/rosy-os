"""Fleet outbound agent stays local-first. There is no fleet server in this repo."""

from rosy_core.fleet_agent.agent import FleetAgent


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
