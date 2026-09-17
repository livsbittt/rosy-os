"""Stage-1 loop wiring. OpenCV stays in an observation adapter, not here."""

from rosy_games.host.hold import HoldObserver
from rosy_games.host.loop import MatchHost, PlayerClient
from rosy_games.host.observer import Observer
from rosy_games.host.robots import MatchSetup, RobotEndpoint, load_match
from rosy_games.host.session import run_match

__all__ = [
    "HoldObserver",
    "MatchHost",
    "MatchSetup",
    "Observer",
    "PlayerClient",
    "RobotEndpoint",
    "load_match",
    "run_match",
]
