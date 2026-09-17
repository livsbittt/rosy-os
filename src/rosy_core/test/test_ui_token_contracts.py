"""concept 16 §10 / D-72 L1 — 표면 토큰 계약.

색의 단일 출처는 `web/tokens.css`다. 이 시험은 `rosy_core`가 소유한 파일만
단언한다(D-73). `rosy_control`의 맵 래스터 색 계약은 별개 파이프라인이며
그 모듈의 시험이 소유한다.
"""

from pathlib import Path
import re

import pytest

WEB_ROOT = Path(__file__).parent.parent / "rosy_core" / "web"
TOKENS = WEB_ROOT / "tokens.css"

COLOR_LITERAL = re.compile(
    r"#[0-9a-fA-F]{3,8}\b|rgba?\(\s*\d|hsla?\(\s*\d"
)
DECLARATION = re.compile(r"^\s*(--[a-z0-9-]+)\s*:", re.MULTILINE)
# 폴백 없는 참조만 위험하다. `var(--x, <fallback>)`는 의도적인 선택 오버라이드이고
# (호스트 카드의 테마 훅), `--meter`처럼 JS가 런타임에 넣는 값도 이 형태를 쓴다.
# 폴백이 없는 `var(--x)`가 선언되지 않으면 그 속성은 조용히 값을 잃는다.
REFERENCE = re.compile(r"var\(\s*(--[a-z0-9-]+)\s*\)")


def tokens_text() -> str:
    return TOKENS.read_text(encoding="utf-8")


def surface_stylesheets() -> list[Path]:
    """토큰 파일을 뺀 표면 스타일시트."""
    return [path for path in sorted(WEB_ROOT.glob("*.css")) if path != TOKENS]


def surface_scripts() -> list[Path]:
    return sorted(WEB_ROOT.glob("*.js"))


def test_tokens_file_is_the_single_source_of_colour():
    assert TOKENS.exists(), "web/tokens.css가 없다"
    declared = set(DECLARATION.findall(tokens_text()))
    assert declared, "tokens.css가 토큰을 하나도 선언하지 않는다"


@pytest.mark.parametrize("path", surface_stylesheets(), ids=lambda p: p.name)
def test_no_raw_colour_outside_the_token_file(path: Path):
    """표면 스타일시트에 원시 색이 있으면 실패한다.

    hex뿐 아니라 `rgba()`/`hsl()`도 원시 색이다. v1 계획이 hex만 셌다가
    37개의 rgba를 놓쳤다 — 같은 종류의 누락을 다시 만들지 않는다.
    """
    found = COLOR_LITERAL.findall(path.read_text(encoding="utf-8"))
    assert not found, f"{path.name}에 원시 색 {len(found)}개: {found[:5]}"


@pytest.mark.parametrize("path", surface_scripts(), ids=lambda p: p.name)
def test_no_raw_colour_in_dashboard_scripts(path: Path):
    """캔버스도 예외가 아니다. 색은 tokens.css에서 읽어 쓴다."""
    found = COLOR_LITERAL.findall(path.read_text(encoding="utf-8"))
    assert not found, f"{path.name}에 원시 색 {len(found)}개: {found[:5]}"


def test_every_referenced_token_is_declared():
    """폴백 없는 `var(--x)` 오타를 잡는다. 선언되지 않으면 조용히 값을 잃는다.

    폴백이 붙은 참조(`var(--surface-raised, var(--sheen-04))`)는 의도적인
    오버라이드 훅이므로 대상이 아니다.
    """
    declared = set(DECLARATION.findall(tokens_text()))
    for path in surface_stylesheets():
        text = path.read_text(encoding="utf-8")
        declared |= set(DECLARATION.findall(text))

    missing: dict[str, set[str]] = {}
    for path in surface_stylesheets():
        used = set(REFERENCE.findall(path.read_text(encoding="utf-8")))
        gap = used - declared
        if gap:
            missing[path.name] = gap

    assert not missing, f"선언되지 않은 토큰 참조: {missing}"


def test_no_token_refers_to_itself():
    """`--paper: var(--paper)`는 CSS에서 무효이고 조용히 값을 잃는다."""
    for path in [TOKENS, *surface_stylesheets()]:
        text = path.read_text(encoding="utf-8")
        for name, value in re.findall(
            r"^\s*(--[a-z0-9-]+)\s*:\s*([^;]+);", text, re.MULTILINE
        ):
            assert f"var({name})" not in value.replace(" ", ""), (
                f"{path.name}: {name}이(가) 자기 자신을 참조한다"
            )


def test_status_colour_never_fills_a_categorical_slot():
    """concept 16 §6 — status 집합은 임계에만 쓴다.

    지도에서 점유 셀과 로봇 위치는 계열·지형이지 임계가 아니다. 예전에는
    둘 다 `#c4db76`(status good)이었고, 그래서 임계 경보가 눈에 띌 대비
    예산이 남지 않았다. costmap lethality만은 실제로 임계이므로 예외다.
    """
    script = (WEB_ROOT / "map.js").read_text(encoding="utf-8")
    block = re.search(r"PALETTE_TOKENS\s*=\s*\{(.*?)\n\};", script, re.DOTALL)
    assert block, "map.js에 PALETTE_TOKENS 선언이 없다"

    bindings = dict(re.findall(r"(\w+)\s*:\s*\"(--[a-z0-9-]+)\"", block.group(1)))
    assert bindings, "PALETTE_TOKENS가 비어 있다"

    categorical = {key: token for key, token in bindings.items() if key != "costLethal"}
    offenders = {
        key: token for key, token in categorical.items() if token.startswith("--status-")
    }
    assert not offenders, f"status 색이 계열·지형 자리에 있다: {offenders}"

    assert bindings.get("costLethal", "").startswith("--status-"), (
        "costmap lethality는 임계이므로 status 토큰이어야 한다"
    )


def test_every_palette_token_map_js_reads_is_declared():
    """map.js가 읽는 토큰이 tokens.css에 없으면 캔버스가 검게 칠해진다."""
    script = (WEB_ROOT / "map.js").read_text(encoding="utf-8")
    block = re.search(r"PALETTE_TOKENS\s*=\s*\{(.*?)\n\};", script, re.DOTALL)
    used = set(re.findall(r"\"(--[a-z0-9-]+)\"", block.group(1)))
    declared = set(DECLARATION.findall(tokens_text()))

    assert used <= declared, f"tokens.css에 없는 토큰: {sorted(used - declared)}"


def test_tokens_are_linked_before_the_surface_stylesheet():
    """토큰이 나중에 로드되면 표면 규칙이 정의되지 않은 값을 먼저 만난다."""
    html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
    tokens_at = html.find("tokens.css")
    styles_at = html.find("styles.css")

    assert tokens_at != -1, "index.html이 tokens.css를 링크하지 않는다"
    assert styles_at != -1
    assert tokens_at < styles_at, "tokens.css가 styles.css보다 먼저 와야 한다"


def test_tokens_css_is_served():
    """allowlist에 없으면 404다 — 링크만으로는 배포되지 않는다."""
    pytest.importorskip("httpx")
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from rosy_core.api.app import create_app

    client = TestClient(create_app({}, SimpleNamespace()))
    response = client.get("/dashboard/assets/tokens.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert "--status-crit" in response.text
