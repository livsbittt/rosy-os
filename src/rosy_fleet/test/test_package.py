"""패키지 뼈대. rosy_fleet 이 import 되고, D-18 대로 rosy_core 스키마를 재사용할 수 있다."""

import xml.etree.ElementTree as ET
from pathlib import Path


def test_package_imports_and_reaches_rosy_core_schemas():
    import rosy_fleet
    from rosy_core.protocol.schemas import SwarmFollowParams

    # 버전은 package.xml, setup.py, __init__.py 세 곳에 있다. 문자열 상수와 비교하면
    # 셋이 어긋나도 통과하므로, 매니페스트를 읽어 그중 하나와는 실제로 맞춘다.
    manifest = Path(rosy_fleet.__file__).resolve().parents[1] / "package.xml"
    assert rosy_fleet.__version__ == ET.parse(manifest).getroot().findtext("version")
    # 값 자체는 rosy_core 의 테스트가 지킨다. 여기서 보는 것은 import 가 닿는다는 것이다.
    assert SwarmFollowParams(target_robot_id="rosy_01").distance == 0.5
