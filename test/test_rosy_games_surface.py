"""D-90: rosy_games is a laptop host, not a CORE slice or image package."""

from robot_contracts import DEPLOY, ROOT, board, hardware_packages


def test_games_is_not_a_runtime_slice_or_hardware_package():
    data = board()
    assert "games" not in data["slices"]["available"]
    assert "games" not in data["slices"]["required"]
    for preset in data["presets"].values():
        assert "games" not in preset
    assert "rosy_games" not in hardware_packages()


def test_core_dockerfile_does_not_copy_games():
    text = (DEPLOY / "Dockerfile").read_text(encoding="utf-8")
    assert "rosy_games" not in text
    assert (ROOT / "src" / "rosy_games" / "package.xml").is_file()
