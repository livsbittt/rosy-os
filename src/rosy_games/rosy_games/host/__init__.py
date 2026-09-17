"""Stage-1 loop wiring. OpenCV stays in an observation adapter, not here."""

from rosy_games.host.loop import MatchHost, PlayerClient
from rosy_games.host.observer import Observer

__all__ = ["MatchHost", "Observer", "PlayerClient"]
