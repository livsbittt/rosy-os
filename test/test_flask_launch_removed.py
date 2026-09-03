"""D-3: navigation web launches must not start the Flask server."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCH = ROOT / "src" / "rosy_navigation" / "launch"

_WEB_LAUNCHES = (
    "web_nav2.launch.xml",
    "web_slam.launch.xml",
    "gz_web_nav2.launch.xml",
    "gz_web_slam.launch.xml",
)


def test_web_launches_do_not_start_flask():
    for name in _WEB_LAUNCHES:
        text = (LAUNCH / name).read_text(encoding="utf-8")
        assert 'exec="nav2_web_server.py"' not in text, name


def test_web_launches_start_rosy_core_instead():
    for name in _WEB_LAUNCHES:
        text = (LAUNCH / name).read_text(encoding="utf-8")
        assert 'pkg="rosy_core"' in text, name
        assert "rosy_core" in text, name
