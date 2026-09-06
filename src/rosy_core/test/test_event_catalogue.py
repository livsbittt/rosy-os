"""§8 이벤트 카탈로그와 코드가 내는 이벤트는 같은 목록이어야 한다.

카탈로그는 "소비자가 의존하는 안정적 계약"이라고 스스로 적어 두었지만 양쪽이
말없이 갈라져 있었다. `docking.*` 11 종과 `battery.deep` 은 구현돼 발행되는데
계약에 없었고 — 계약만 읽는 Fleet 은 도킹 상태도, 딥 방전으로 모터가 선 이유도
알 방법이 없다 — `safety.watchdog` 은 v1.0 부터 약속돼 있는데 코드가 낸 적이
없었다. D-31 과 D-32 가 각각 라우트와 응답에 대해 고친 것과 같은 어긋남이다.

**이 파일이 손으로 관리하는 목록을 갖지 않는 것이 핵심이다.** 앞선 판본은
"이벤트처럼 생긴 문자열"을 모으고 예외 목록으로 걸러냈는데, 그 예외 목록이
`battery.deep`(critical)을 숨겼다 — 문서와 똑같이 드리프트한 것이다. 지금은
발행 지점 자체에서 이름·심각도·payload 키를 읽는다. 새 이벤트 계열이 생겨도,
키 하나가 바뀌어도 걸린다.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parents[1] / "rosy_core"
REFERENCE = ROOT / "docs" / "reference" / "ROSY API & Protocol Reference.md"

_EVENT_NAME = re.compile(r"[a-z_]+\.[a-z_]+")
_SEVERITIES = {"info", "warning", "error", "critical"}


class Emit:
    """발행 지점 하나에서 읽어낸 것."""

    def __init__(self, name: str, severity: str | None,
                 keys: frozenset[str] | None, where: str) -> None:
        self.name = name
        self.severity = severity
        self.keys = keys          # None = 동적으로 만든 payload, 키를 알 수 없음
        self.where = where

    def __repr__(self) -> str:  # pragma: no cover - 실패 메시지용
        return f"{self.name} @ {self.where}"


def _names_in(node: ast.AST) -> list[str]:
    """이벤트 **이름 자리**의 문자열만. payload 안의 값은 세지 않는다.

    `publish("config.changed", data={"key": "safety.limits"})` 에서
    `safety.limits` 는 설정 키이지 이벤트가 아니다. 이름 자리만 보면 그런 것을
    걸러내려고 예외 목록을 둘 이유가 없어진다 — 그 목록이 지난번에 실제
    이벤트를 하나 숨겼다.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value] if _EVENT_NAME.fullmatch(node.value) else []
    if isinstance(node, ast.IfExp):
        # self._emit("docking.charging" if confirmed else "docking.charge_lost", ...)
        return _names_in(node.body) + _names_in(node.orelse)
    return []


def emit_sites() -> list[Emit]:
    sites: list[Emit] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            first: ast.AST | None = None
            rest: list[ast.AST] = []
            if isinstance(node, ast.Call):
                func = node.func
                called = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                if called in {"publish", "_emit"} and node.args:
                    first, rest = node.args[0], list(node.args[1:]) + [k.value for k in node.keywords]
            elif isinstance(node, ast.Tuple) and 2 <= len(node.elts) <= 3:
                # 절전·배터리는 `(type, severity, data)` 튜플을 모아 두었다가
                # 한 번에 낸다 — append 로도, 리스트 리터럴로도. 호출 모양을
                # 하나씩 세는 대신 튜플 자체를 알아본다.
                first, rest = node.elts[0], list(node.elts[1:])
            names = _names_in(first) if first is not None else []
            if not names:
                continue

            severity = next(
                (a.value for a in rest
                 if isinstance(a, ast.Constant) and a.value in _SEVERITIES), None)
            if severity is None:
                severity = next(
                    (a.attr.lower() for a in rest
                     if isinstance(a, ast.Attribute) and a.attr.lower() in _SEVERITIES), None)
            payload = next((a for a in rest if isinstance(a, ast.Dict)), None)
            keys: frozenset[str] | None = None
            if payload is not None:
                literal = [k.value for k in payload.keys
                           if isinstance(k, ast.Constant) and isinstance(k.value, str)]
                if len(literal) == len(payload.keys):
                    keys = frozenset(literal)
            where = f"{path.name}:{node.lineno}"
            sites.extend(Emit(name, severity, keys, where) for name in names)
    return sites


#: `type` 열 한 칸에 여러 이벤트가 들어가는 행이 있다.
_ROW = re.compile(r"^\|\s*(?P<types>(?:`[a-z_]+\.[a-z_/]+`[^|`]*)+)\|"
                  r"\s*(?P<severity>[^|]*)\|\s*(?P<sender>[^|]*)\|(?P<payload>.*)$",
                  re.MULTILINE)


class Row:
    def __init__(self, severity: str, sender: str, payload: str) -> None:
        self.severity = severity.strip()
        self.sender = sender.strip()
        self.payload = payload

    @property
    def keys(self) -> set[str]:
        """문서가 적은 payload 키. `{goal\\|waypoint, duration_ms}` → 세 개."""
        match = re.search(r"\{([^}]*)\}", self.payload)
        if not match:
            return set()
        parts = re.split(r"[,|]", match.group(1).replace("\\", ""))
        return {p.strip().strip("`?").strip() for p in parts if p.strip()}

    @property
    def unimplemented(self) -> bool:
        return "미구현" in self.payload

    @property
    def robot_sent(self) -> bool:
        return "로봇" in self.sender


def catalogue() -> dict[str, Row]:
    text = REFERENCE.read_text(encoding="utf-8")
    start = text.index("# 8. 이벤트 카탈로그")
    section = text[start:text.index("\n# ", start + 10)]
    rows: dict[str, Row] = {}
    for match in _ROW.finditer(section):
        row = Row(match.group("severity"), match.group("sender"), match.group("payload"))
        for quoted in re.findall(r"`([a-z_]+\.[a-z_/]+)`", match.group("types")):
            head, _, rest = quoted.partition(".")
            for leaf in rest.split("/"):
                rows[f"{head}.{leaf}"] = row
    return rows


def test_the_catalogue_is_not_a_wish_list():
    """로봇이 낸다고 적힌 것은 코드에 있어야 한다.

    `safety.watchdog` 은 v1.0 부터 여기 있었고 코드에는 없었다. 계약을 읽고
    `safety.*` 를 구독한 쪽은 조종이 끊겨 로봇이 서도 아무 신호를 받지 못했다.
    """
    emitted = {site.name for site in emit_sites()}
    promised = {name for name, row in catalogue().items()
                if row.robot_sent and not row.unimplemented}

    assert not promised - emitted, (
        "카탈로그가 약속하는데 코드가 내지 않는다: " + ", ".join(sorted(promised - emitted))
    )


def test_nothing_is_emitted_behind_the_contract():
    """코드가 내는 것은 카탈로그에 있어야 한다.

    `docking.*` 11 종과 `battery.deep` 이 그랬다. 문서화되지 않은 이벤트는 §1 의
    폐기 정책 바깥에 있어, 언제 사라져도 아무도 약속을 깬 것이 아니게 된다.
    """
    documented = set(catalogue())
    undocumented = sorted({site.name for site in emit_sites()} - documented)

    assert not undocumented, "코드가 내는데 카탈로그에 없다: " + ", ".join(undocumented)


def test_every_documented_payload_key_is_one_the_code_sends():
    """`{}` 안에 적힌 키는 실제로 실려야 한다.

    `nav.stuck` 은 `{timeout_ms}` 로 적혀 있었고 코드는 `timeout_s` 를 보냈다.
    계약대로 읽은 소비자는 KeyError 를 받는다.
    """
    sent: dict[str, set[str]] = {}
    for site in emit_sites():
        if site.keys is not None:
            sent.setdefault(site.name, set()).update(site.keys)

    wrong: list[str] = []
    for name, row in catalogue().items():
        if name not in sent or row.unimplemented:
            continue
        for key in row.keys - sent[name]:
            wrong.append(f"{name}: 문서에 있는 '{key}' 를 코드가 보내지 않는다")

    assert not wrong, "\n".join(wrong)


def test_every_key_the_code_sends_is_documented():
    documented = catalogue()
    missing: list[str] = []
    for site in emit_sites():
        row = documented.get(site.name)
        if row is None or site.keys is None:
            continue
        for key in site.keys - row.keys:
            missing.append(f"{site.name} ({site.where}): '{key}' 가 문서에 없다")

    assert not missing, "\n".join(missing)


def test_the_documented_severity_is_the_one_the_code_uses():
    """심각도는 소비자가 경보를 거는 기준이다. 장식이 아니다."""
    documented = catalogue()
    wrong: list[str] = []
    for site in emit_sites():
        row = documented.get(site.name)
        if row is None or site.severity is None:
            continue
        if site.severity not in row.severity:
            wrong.append(f"{site.name} ({site.where}): 코드 {site.severity}, 문서 {row.severity}")

    assert not wrong, "\n".join(wrong)


def test_an_event_this_package_emits_is_marked_as_the_robot_sending_it():
    """발신 열을 잘못 적는 것이 가장 조용한 드리프트다.

    로봇 이벤트를 `Fleet` 으로 바꿔 적으면 `robot_sent` 가 거짓이 되어 wish-list
    검사에서 빠지고, 그 행은 양방향 모두에서 감시 밖으로 나간다 — 한 칸을
    고쳐 쓰는 것으로 가드가 그 이벤트를 통째로 놓게 된다.
    """
    documented = catalogue()
    mislabelled = sorted({
        site.name for site in emit_sites()
        if site.name in documented and not documented[site.name].robot_sent
    })

    assert not mislabelled, (
        "이 패키지가 내는데 발신이 로봇이 아니라고 적혀 있다: " + ", ".join(mislabelled)
    )


def test_the_fleet_rows_are_excluded_by_their_sender_column():
    """`mission.*` 는 Fleet 이 낸다. 하드코딩한 예외가 아니라 표가 정한다."""
    rows = catalogue()

    assert rows["mission.assigned"].sender == "Fleet"
    assert not rows["mission.assigned"].robot_sent
    assert rows["safety.estop"].robot_sent


def test_the_extractor_reads_the_shapes_this_package_actually_uses():
    """추출기가 조용히 아무것도 못 찾으면 위의 모든 검사가 공허해진다."""
    sites = emit_sites()
    names = {site.name for site in sites}

    assert len(names) >= 30, f"only found {len(names)}"
    # 직접 호출, 튜플 수집, 조건식 이름 — 세 가지 모양이 모두 잡혀야 한다.
    assert "nav.started" in names            # publish("...", data={...})
    assert "power.mode_changed" in names     # pending.append((...))
    assert "docking.charge_lost" in names    # "a" if cond else "b"
    assert any(site.keys for site in sites if site.name == "safety.watchdog")


@pytest.mark.parametrize("event", ["battery.deep", "safety.watchdog", "docking.failed"])
def test_the_events_this_change_was_about_are_covered(event):
    """회귀 방지: 이 셋이 각각 이 파일이 존재하는 이유다."""
    assert event in catalogue()
    assert event in {site.name for site in emit_sites()}
