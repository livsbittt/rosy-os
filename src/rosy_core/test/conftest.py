"""테스트가 로봇 한 대를 세우는 방법은 한 곳에만 있어야 한다.

`CoreServices.build` 의 배선은 계속 늘어난다 — 도킹 provider, 세션 종료
리스너, e-stop 리스너가 이번에 붙었다. 파일마다 복사해 두면 그중 하나만
빠뜨렸을 때 테스트는 통과하면서 실제 배선과 어긋난다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytest
import yaml

CONFIG_DIR = Path(__file__).parent.parent / "config"

# Opt-in advertisement for tests that exercise Nav2/SLAM/swarm routes.
# Packaged capabilities.yaml follows runtime.mode core and keeps those flags off.
SERVING_CAPS = {
    "navigation": {
        "goal_navigation": True,
        "return_home": True,
        "max_linear_velocity": 0.20,
        "max_angular_velocity": 0.80,
    },
    "teleop": True,
    "slam": True,
    "swarm": {"follow": True, "lead": True},
}


@pytest.fixture
def core_client(tmp_path):
    """`(TestClient, CoreServices)` 를 만드는 팩토리.

    capability 나 설정을 바꿔 끼우는 것이 이 팩토리를 두는 이유다 — "미지원
    로봇은 501" 같은 계약은 지원 로봇에서는 확인할 수 없다.
    """
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from rosy_core.api.app import create_app
    from rosy_core.profile import RobotProfile
    from rosy_core.services import CoreServices

    def build(*, capabilities: Optional[dict] = None,
              config_overrides: Optional[dict] = None):
        def read(name):
            return yaml.safe_load((CONFIG_DIR / name).read_text(encoding="utf-8"))

        config = read("rosy_default.yaml")
        caps = read("capabilities.yaml")
        profile = RobotProfile.load(CONFIG_DIR / "profile.pinky_pro.yaml")
        if capabilities:
            caps.update(capabilities)
        if config_overrides:
            config.update(config_overrides)
        services = CoreServices.build(config, profile, caps, tmp_path / "wp.json")
        return TestClient(create_app(config, services)), services

    return build
