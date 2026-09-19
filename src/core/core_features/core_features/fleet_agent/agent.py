"""Outbound Fleet WebSocket is not started. This robot is local-first (D-5).

There is no Fleet server in this repository. Teleop, navigation, and safety
must not wait for this agent.
"""


class FleetAgent:
    def __init__(self) -> None:
        self.enabled = False
        self.connected = False

    def start(self) -> None:
        return

    def stop(self) -> None:
        self.connected = False

    def _connect(self, url: str) -> None:
        raise RuntimeError("fleet outbound is not enabled")
