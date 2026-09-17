"""colcon install 없이 pytest를 돌린다 (Windows/CI)."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
entry = str(SRC / "rosy_games")
if entry not in sys.path:
    sys.path.insert(0, entry)
