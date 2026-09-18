"""D-90: rosy_games is a laptop host, not a CORE slice or image package."""

from robot_contracts import DEPLOY, ROOT, board, hardware_packages


def test_games_is_not_a_runtime_slice_or_hardware_package():
    data = board()
    assert "games" not in data["slices"]["available"]
    assert "games" not in data["slices"]["required"]
    for preset in data["presets"].values():
        assert "games" not in preset
    assert "rosy_games" not in hardware_packages()


def test_games_overhead_cv2_does_not_close_the_robot_camera_adr():
    """D-94: 노트북 천장 웹캠 ≠ D-41 ARM64 카메라 배치."""
    overhead = ROOT / "src" / "rosy_games" / "rosy_games" / "host" / "overhead.py"
    assert "import cv2" in overhead.read_text(encoding="utf-8")
    homography = ROOT / "src" / "rosy_games" / "rosy_games" / "field" / "homography.py"
    assert "cv2" not in homography.read_text(encoding="utf-8")
    adr = (ROOT / "docs" / "reference" / "ROSY ADR Log.md").read_text(encoding="utf-8")
    row = next(line for line in adr.splitlines() if line.startswith("| D-41 |"))
    assert "Proposed" in row
    core = ROOT / "src" / "rosy_core" / "rosy_core"
    for path in core.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "import cv2" not in text and "from cv2" not in text, path


def test_core_dockerfile_does_not_copy_games():
    text = (DEPLOY / "Dockerfile").read_text(encoding="utf-8")
    assert "rosy_games" not in text
    assert (ROOT / "src" / "rosy_games" / "package.xml").is_file()


def test_games_board_is_not_the_core_dashboard():
    """D-101: 축구 보드는 노트북 게임 표면. CORE /dashboard 자산이 아니다."""
    core_web = ROOT / "src" / "rosy_core" / "rosy_core" / "web"
    games_web = ROOT / "src" / "rosy_games" / "rosy_games" / "web"
    assert (games_web / "index.html").is_file()
    assert (games_web / "board.js").is_file()
    core_html = (core_web / "index.html").read_text(encoding="utf-8")
    assert "soccer" not in core_html.lower()
    assert "골 20" not in core_html
    app = (ROOT / "src" / "rosy_core" / "rosy_core" / "api" / "app.py").read_text(encoding="utf-8")
    assert "board.js" not in app
    styles = (games_web / "styles.css").read_text(encoding="utf-8")
    assert "tokens.css" not in styles
    assert "/dashboard/assets" not in styles
