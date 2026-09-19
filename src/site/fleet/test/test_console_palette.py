"""concept 16 §6, §7.3 / D-72 L1 / D-82 — 관제 표면 팔레트의 수치 게이트.

L1(토큰)은 네 표면이 공유하지만 컴포넌트는 공유하지 않는다. 이 모듈은 자기
토큰 사본을 갖고 있으므로(D-73: 기능 시험은 그 모듈이 소유한 코드만 단언한다)
같은 성질을 여기서 따로 지킨다.

이 시험이 존재하는 이유: Fleet은 D-82 이전 팔레트를 복사해 갔었다. 적록 색약
시야에서 주의 대 위험 대비가 1.07:1이었고, 계열 색 하나가 따뜻한 띠에 있었으며,
로봇 식별 4색 중 6쌍 가운데 4쌍이 색약에서 갈리지 않았다. 관제는 색 예산이
가장 빡빡한 표면이다 — 스무 대 중 한 대가 문제면 색이 있는 줄도 하나여야 한다.

표준 라이브러리만 쓴다.
"""

from itertools import combinations
from pathlib import Path
import math
import re

import pytest

WEB = Path(__file__).resolve().parents[1] / "fleet" / "server" / "web"
TOKENS = WEB / "tokens.css"

COLOR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\(\s*\d|hsla?\(\s*\d")
ROBOTS = ("robot-1", "robot-2", "robot-3")


def _linear(channel: int) -> float:
    v = channel / 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _encode(value: float) -> int:
    value = max(0.0, min(1.0, value))
    srgb = 12.92 * value if value <= 0.0031308 else 1.055 * value ** (1 / 2.4) - 0.055
    return max(0, min(255, round(srgb * 255)))


def _rgb(hex_colour: str):
    raw = hex_colour.lstrip("#")
    return tuple(_linear(int(raw[i:i + 2], 16)) for i in (0, 2, 4))


def oklch(hex_colour: str):
    r, g, b = _rgb(hex_colour)
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    lightness = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    bb = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return lightness, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360


def contrast(a: str, b: str) -> float:
    def lum(c):
        r, g, bl = _rgb(c)
        return 0.2126 * r + 0.7152 * g + 0.0722 * bl
    ya, yb = lum(a), lum(b)
    return (max(ya, yb) + 0.05) / (min(ya, yb) + 0.05)


def deuteranope(hex_colour: str) -> str:
    r, g, b = _rgb(hex_colour)
    return "#%02x%02x%02x" % (
        _encode(0.625 * r + 0.375 * g),
        _encode(0.700 * r + 0.300 * g),
        _encode(0.300 * g + 0.700 * b),
    )


@pytest.fixture(scope="module")
def palette() -> dict[str, str]:
    found = dict(
        re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;", TOKENS.read_text(encoding="utf-8"))
    )
    assert found, "fleet tokens.css에서 hex 토큰을 읽지 못했다"
    return found


def surfaces() -> list[Path]:
    return [WEB / "styles.css", WEB / "console.js"]


@pytest.mark.parametrize("path", surfaces(), ids=lambda p: p.name)
def test_tokens_are_the_single_source_of_colour(path: Path):
    found = COLOR_LITERAL.findall(path.read_text(encoding="utf-8"))
    assert not found, f"{path.name}에 원시 색 {len(found)}개: {found[:5]}"


def test_caution_and_danger_never_collapse(palette):
    warn, crit = palette["status-warn"], palette["status-crit"]
    delta_l = abs(oklch(warn)[0] - oklch(crit)[0])
    assert delta_l >= 0.15, f"주의·위험 지각 밝기 차 {delta_l:.3f} (이전 사본 0.131)"

    simulated = contrast(deuteranope(warn), deuteranope(crit))
    assert simulated >= 2.0, f"색약 대비 {simulated:.2f}:1 (이전 사본 1.07)"


def test_status_is_warm_and_series_is_cool(palette):
    for name in ("status-warn", "status-crit"):
        hue = oklch(palette[name])[2]
        assert hue <= 90 or hue >= 350, f"{name} 색상 {hue:.0f} — status는 따뜻한 띠"
    for name in ("series-primary", "series-goal", *ROBOTS):
        hue = oklch(palette[name])[2]
        assert 150 <= hue <= 330, f"{name} 색상 {hue:.0f} — series는 차가운 띠"


def test_robot_identity_is_a_lightness_ladder(palette):
    """네 대를 네 색상으로 가르는 것은 sRGB에서 불가능하다.

    식별은 라벨(PINKY-01)이 나르고, 색은 같은 색상의 밝기 사다리다. 밝기
    차이는 색약·글레어·흑백에서도 남는다.
    """
    hues = [oklch(palette[name])[2] for name in ROBOTS]
    assert max(hues) - min(hues) <= 5, f"로봇 사다리가 한 색상이 아니다: {[round(h) for h in hues]}"

    lightness = [oklch(palette[name])[0] for name in ROBOTS]
    assert lightness == sorted(lightness, reverse=True), (
        f"밝기 사다리가 단조가 아니다: {[round(v, 2) for v in lightness]}"
    )

    ground = palette["ground"]
    for name in ROBOTS:
        ratio = contrast(palette[name], ground)
        assert ratio >= 3.0, f"{name}이 바탕 위에서 {ratio:.2f}:1 — 표식은 3:1이 필요하다"

    for a, b in zip(ROBOTS, ROBOTS[1:]):
        ratio = contrast(deuteranope(palette[a]), deuteranope(palette[b]))
        assert ratio >= 1.5, f"{a} 대 {b} 색약 대비 {ratio:.2f}:1"


def test_nominal_carries_no_colour(palette):
    """concept 16 §7.3 — 정상은 화면에 없다. 초록이 아니라 없음이다."""
    text = TOKENS.read_text(encoding="utf-8")
    assert "--status-good" not in text, "관제 팔레트에 '정상' 색이 남아 있다"
    for path in surfaces():
        body = path.read_text(encoding="utf-8")
        assert "--status-good" not in body, f"{path.name}이 정상을 색으로 칠한다"


def test_no_decoration_effects(palette):
    banned = ("linear-gradient", "radial-gradient", "drop-shadow(")
    for path in surfaces():
        body = path.read_text(encoding="utf-8")
        hits = [token for token in banned if token in body]
        assert not hits, f"{path.name}에 장식 효과: {hits}"


def test_text_meets_wcag_on_the_ground(palette):
    ground = palette["ground"]
    for name in ("paper", "muted", "status-warn", "series-primary", "series-goal"):
        ratio = contrast(palette[name], ground)
        assert ratio >= 4.5, f"{name} 대비 {ratio:.2f}:1"
    # 위험은 글자가 아니라 채움이다 — 잉크를 얹을 수 있으면 된다.
    assert contrast(palette["paper"], palette["status-crit"]) >= 4.5


def test_every_referenced_token_is_declared(palette):
    """토큰을 갈아끼울 때 관제 UI가 조용히 색을 잃지 않게 한다.

    `var(--x)`와 `css("--x")` 둘 다 본다 — 콘솔은 CSP 아래에서 캔버스 색을
    런타임에 읽으므로, 선언이 사라지면 지도가 검게 칠해진다.
    """
    declared = set(
        re.findall(r"--([a-z0-9-]+)\s*:", TOKENS.read_text(encoding="utf-8"))
    )
    missing: dict[str, list[str]] = {}
    for path in surfaces():
        body = path.read_text(encoding="utf-8")
        used = set(re.findall(r"var\(\s*--([a-z0-9-]+)\s*\)", body))
        used |= set(re.findall(r'css\("--([a-z0-9-]+)"\)', body))
        gap = sorted(used - declared)
        if gap:
            missing[path.name] = gap
    assert not missing, f"선언되지 않은 토큰 참조: {missing}"

