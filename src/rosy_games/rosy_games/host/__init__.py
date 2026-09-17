"""Stage-1 loop wiring. OpenCV stays in an observation adapter, not here."""

from rosy_games.host.loop import MatchHost, ObservationSource, PlayerClient

__all__ = ["MatchHost", "ObservationSource", "PlayerClient"]

