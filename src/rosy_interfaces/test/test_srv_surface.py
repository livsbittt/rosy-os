"""Interface-only surface: the .srv files this package ships (D-73)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRV = ROOT / "srv"
EXPECTED = ("Emotion.srv", "SetBrightness.srv", "SetLamp.srv", "SetLed.srv")


def test_service_definitions_exist_and_are_nonempty():
    names = {path.name for path in SRV.glob("*.srv")}
    assert set(EXPECTED) <= names
    for name in EXPECTED:
        text = (SRV / name).read_text(encoding="utf-8").strip()
        assert text, f"{name} is empty"
        assert "---" in text
