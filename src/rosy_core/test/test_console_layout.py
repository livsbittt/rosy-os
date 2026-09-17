"""concept 16 §7.1/§7.2 / D-77 — 운용 콘솔은 공간 문법, 점검은 절차 문법이다.

한 화면에 두 문법을 섞지 않는다(§4 L2). 이 시험은 그 분리를 구조로 지킨다.
CI에 브라우저가 없으므로 배치 자체는 잴 수 없다 — 대신 배치를 성립시키는
**구조와 규칙**을 단언한다. 실제 렌더 측정은 Playwright로 따로 했고, 그때
잡힌 결함들이 아래 각 단언의 이유다.
"""

from pathlib import Path
import re

WEB_ROOT = Path(__file__).parent.parent / "rosy_core" / "web"
INDEX = WEB_ROOT / "index.html"
STYLES = WEB_ROOT / "styles.css"
APP = WEB_ROOT / "app.js"


def html() -> str:
    return INDEX.read_text(encoding="utf-8")


def css() -> str:
    return STYLES.read_text(encoding="utf-8")


def test_the_two_grammars_live_in_separate_containers():
    markup = html()
    assert 'id="view-operate-panel"' in markup and 'class="console"' in markup
    assert 'id="view-inspect-panel"' in markup and 'class="inspect"' in markup


def test_the_console_holds_the_three_regions_in_order():
    markup = html()
    order = [m for m in re.findall(r"region region-(sense|observe|act)", markup)]
    assert order == ["sense", "observe", "act"], f"영역 순서가 감지·관측·조작이 아니다: {order}"


def test_the_operator_panels_are_in_the_console_and_the_rest_in_inspect():
    markup = html()
    console = markup.split('id="view-operate-panel"')[1].split('id="view-inspect-panel"')[0]
    inspect = markup.split('id="view-inspect-panel"')[1]
    for panel in ("motion-panel", "field-map-panel", "control-panel", "capability-panel"):
        assert panel in console, f"{panel}이 운용 화면에 없다"
    for panel in ("system-panel", "host-panel", "ros-network-panel", "field-settings-panel"):
        assert panel in inspect, f"{panel}이 점검 화면에 없다"


def test_a_hidden_view_does_not_take_layout():
    """`display`를 지정한 요소에는 `[hidden]`의 display:none이 진다.

    그 버그로 숨긴 점검 뷰가 레이아웃을 차지해 페이지가 3582px 스크롤했고
    지도가 24px로 눌렸다. 측정으로 확인했고, 이 규칙이 그걸 막는다.
    """
    assert re.search(r"\[hidden\]\s*\{[^}]*display:\s*none\s*!important", css()), (
        "[hidden]을 display:none !important로 고정하는 규칙이 없다"
    )


def test_the_console_does_not_scroll():
    """위치가 기억이다. 콘솔이 스크롤하면 그 약속이 깨진다."""
    rule = re.search(r"\.console\s*\{([^}]*)\}", css())
    assert rule, ".console 규칙이 없다"
    body = rule.group(1)
    assert "100vh" in body and "--topbar-height" in body, "콘솔 높이가 뷰포트에 묶여 있지 않다"
    assert "overflow: hidden" in body
    # 꼬리말은 스크롤하는 점검 뷰의 것이다 — 운용에서 64px을 가져가면 그만큼
    # 지도가 줄어든다. 클래스 셀렉터여야 한다(`#page-footer`는 존재하지 않는다).
    assert 'body[data-view="operate"] .page-footer' in css()


def test_only_the_sense_region_may_scroll():
    """내용이 넘치면 감지만 스크롤하고 관측·조작은 고정된다(§7.1)."""
    observe = re.search(r"\.region-observe\s*\{([^}]*)\}", css())
    assert observe and "overflow-y: auto" not in observe.group(1)


def test_the_irreversible_control_comes_first_in_the_act_region():
    """비상정지가 teleop 뒤에 있으면 화면 밖으로 밀린다 — 실제로 y=832였다.
    자리도 탭 순서도 첫째여야 한다."""
    markup = html()
    control = markup.split('class="panel control-panel"')[1].split("</section>")[0]
    assert control.index("safety-actions") < control.index("teleop-commissioning")


def test_the_view_switch_is_wired_and_defaults_to_operate():
    app = APP.read_text(encoding="utf-8")
    assert 'showView("operate")' in app, "기본 뷰를 운용으로 두지 않는다"
    assert 'elements["view-inspect"].addEventListener' in app
    assert 'document.body.dataset.view' in app, "꼬리말 규칙이 기대는 페이지 상태가 없다"
