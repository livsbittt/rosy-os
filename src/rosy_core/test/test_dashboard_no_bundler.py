"""D-75: robot-local UI is hand-written static assets, not a React/Vite build."""

from pathlib import Path

CORE = Path(__file__).resolve().parents[1]


def test_rosy_core_has_no_frontend_bundler():
    assert not (CORE / "package.json").exists()
    assert not list(CORE.glob("vite.config.*"))
    assert not list(CORE.glob("**/webpack.config.*"))
    web = CORE / "rosy_core" / "web"
    assert (web / "index.html").is_file()
    assert (web / "styles.css").is_file()


def test_dashboard_assets_are_an_explicit_allowlist():
    app = (CORE / "rosy_core" / "api" / "app.py").read_text(encoding="utf-8")
    assert "dashboard_assets" in app
    assert '"styles.css"' in app
    assert '"app.js"' in app
    assert "index.html" in app
