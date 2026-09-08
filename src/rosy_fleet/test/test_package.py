"""패키지 뼈대. rosy_fleet 이 import 되고, D-18 대로 rosy_core 스키마를 재사용할 수 있다."""


def test_package_imports_and_reaches_rosy_core_schemas():
    import rosy_fleet
    from rosy_core.protocol.schemas import SwarmFollowParams

    assert rosy_fleet.__version__ == "0.1.0"
    assert SwarmFollowParams(target_robot_id="rosy_01").distance == 0.5
