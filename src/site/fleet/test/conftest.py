"""colcon install 없이 pytest 를 돌린다 (Windows/CI).

`fleet` 은 `core_common.protocol.schemas` 를 import 한다(D-18). 두 패키지 모두
소스 트리에서 바로 찾도록 sys.path 를 잡는다 — 루트 `test/conftest.py` 가
`deploy/release` 에 하는 것과 같은 방식이다.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]

for path in (SRC / "fleet", SRC / "core"):
    entry = str(path)
    if entry not in sys.path:
        sys.path.insert(0, entry)
