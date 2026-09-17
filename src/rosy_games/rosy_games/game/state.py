from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from rosy_games.game.protocol import Phase


@dataclass(frozen=True)
class MatchState:
    phase: Phase
    score: Mapping[str, int]
    reason: str = ""
    scorer: Optional[str] = None
