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


def test_core_has_no_soccer_robot_mode():
    """D-90: RobotMode.SOCCER 없음."""
    schemas = (ROOT / "src" / "rosy_core" / "rosy_core" / "protocol" / "schemas.py").read_text(
        encoding="utf-8"
    )
    assert "SOCCER" not in schemas


def test_fleet_does_not_own_the_match_and_games_has_no_fleet_start():
    """D-106: 매치 시작 버튼은 지금 없다. fleet↛games, 보드는 Fleet UI가 아니다."""
    fleet = ROOT / "src" / "rosy_fleet" / "rosy_fleet"
    for path in fleet.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "rosy_games" not in text, path
    for path in fleet.rglob("*.html"):
        text = path.read_text(encoding="utf-8").lower()
        assert "soccer" not in text
        assert "rosy_games" not in text
    games_web = ROOT / "src" / "rosy_games" / "rosy_games" / "web" / "index.html"
    html = games_web.read_text(encoding="utf-8").lower()
    assert "fleet" not in html
    cli = (ROOT / "src" / "rosy_games" / "rosy_games" / "cli.py").read_text(encoding="utf-8")
    assert "rosy_fleet" not in cli
    loop = (ROOT / "src" / "rosy_games" / "rosy_games" / "host" / "loop.py").read_text(encoding="utf-8")
    assert "def reset(" in loop


def test_deferred_soccer_track_is_not_in_the_tree():
    """D-97/D-98/D-99/D-109: onboard·isaac·neural 없음. D-41은 Proposed."""
    games = ROOT / "src" / "rosy_games" / "rosy_games"
    assert not (games / "host" / "onboard.py").is_file()
    assert not (games / "isaac").exists()
    assert not (games / "policy" / "neural.py").is_file()
    cli = (games / "cli.py").read_text(encoding="utf-8")
    assert "onboard" not in cli
    adr = (ROOT / "docs" / "reference" / "ROSY ADR Log.md").read_text(encoding="utf-8")
    row = next(line for line in adr.splitlines() if line.startswith("| D-41 |"))
    assert "Proposed" in row


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
