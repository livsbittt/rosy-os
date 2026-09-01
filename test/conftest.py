"""Make the release tooling importable from the contract tests.

``deploy/release`` is shipped as scripts on the build host rather than as an
installed package, so it is not on ``sys.path``. Bootstrapping it here keeps
the test modules free of import-order gymnastics.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

for path in (ROOT / "deploy" / "release",):
    entry = str(path)
    if entry not in sys.path:
        sys.path.insert(0, entry)
