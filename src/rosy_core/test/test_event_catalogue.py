"""§8 이벤트 카탈로그와 코드가 내는 이벤트는 같은 목록이어야 한다.

카탈로그는 "소비자가 의존하는 안정적 계약"이라고 스스로 적어 두었지만, 양쪽이
말없이 갈라져 있었다. `docking.*` 11 종은 구현돼 발행되는데 계약에 없었고 —
계약만 읽는 Fleet 은 도킹 상태를 알 방법이 없다 — `safety.watchdog` 은 v1.0
부터 약속돼 있는데 코드가 낸 적이 없었다. D-31 과 D-32 가 각각 라우트와 응답에
대해 고친 것과 같은 어긋남이다.

문서를 한 번 맞추는 것은 다시 갈라지는 것을 막지 못한다. 이 테스트가 막는다.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parents[1] / "rosy_core"
REFERENCE = ROOT / "docs" / "reference" / "ROSY API & Protocol Reference.md"

#: `type` 열의 한 칸에 여러 이벤트가 들어가는 행이 있다:
#: `waypoint.created/updated/deleted`, `slam.started` / `slam.stopped`.
_ROW = re.compile(r"^\|\s*(?P<types>(?:`[a-z_]+\.[a-z_/]+`\s*/?\s*)+)\|"
                  r"\s*(?P<severity>[^|]*)\|\s*(?P<sender>[^|]*)\|",
                  re.MULTILINE)


def _expand(cell: str) -> set[str]:
    """`waypoint.created/updated/deleted` → 세 이벤트."""
    names: set[str] = set()
    for quoted in re.findall(r"`([a-z_]+\.[a-z_/]+)`", cell):
        head, _, rest = quoted.partition(".")
        for leaf in rest.split("/"):
            names.add(f"{head}.{leaf}")
    return names


def catalogue() -> dict[str, str]:
    """이벤트 → 발신 주체. 카탈로그는 Fleet 이 내는 것도 함께 싣는다."""
    text = REFERENCE.read_text(encoding="utf-8")
    start = text.index("# 8. 이벤트 카탈로그")
    section = text[start:text.index("\n# ", start + 10)]
    found: dict[str, str] = {}
    for row in _ROW.finditer(section):
        sender = row.group("sender").strip()
        for name in _expand(row.group("types")):
            found[name] = sender
    return found


def emitted() -> set[str]:
    """패키지가 이벤트로 낼 수 있는 모든 이름.

    `publish("x.y", ...)` 만 찾으면 부족하다 — 도킹과 절전은 `(type, severity,
    data)` 튜플을 모아 한 번에 내보내므로, 호출 자리에 문자열이 없다. 그래서
    이벤트처럼 생긴 문자열 상수를 모두 모으고, 이벤트가 아닌 것을 걷어낸다.
    """
    prefixes = {"system", "config", "mode", "nav", "safety", "battery", "command",
                "waypoint", "slam", "power", "presence", "map", "docking",
                "localization", "swarm"}
    #: 같은 모양이지만 이벤트가 아닌 것: capability 경로, 설정 키, 파일 이름.
    not_events = {"safety.limits", "swarm.follow", "swarm.lead", "docking.supported",
                  "map.js", "battery.deep", "power.mode", "nav.state"}
    names: set[str] = set()
    for path in PACKAGE.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value
                if (re.fullmatch(r"[a-z_]+\.[a-z_]+", value)
                        and value.split(".")[0] in prefixes
                        and value not in not_events):
                    names.add(value)
    return names


def robot_side() -> set[str]:
    """카탈로그가 로봇이 낸다고 적은 것만. Fleet 행은 이 저장소의 몫이 아니다."""
    return {name for name, sender in catalogue().items() if "로봇" in sender}


def test_the_catalogue_is_not_a_wish_list():
    """로봇이 낸다고 적힌 것은 코드에 있어야 한다.

    `safety.watchdog` 은 v1.0 부터 여기 있었고 코드에는 없었다. 계약을 읽고
    `safety.*` 를 구독한 쪽은 조종이 끊겨 로봇이 서도 아무 신호를 받지 못했다.
    """
    promised = robot_side() - emitted()
    unimplemented = {name for name, sender in catalogue().items()
                     if "미구현" in sender or "미구현" in _row_note(name)}

    assert promised <= unimplemented, (
        "카탈로그가 약속하는데 코드가 내지 않는다: " + ", ".join(sorted(promised - unimplemented))
    )


def _row_note(name: str) -> str:
    text = REFERENCE.read_text(encoding="utf-8")
    start = text.index("# 8. 이벤트 카탈로그")
    section = text[start:text.index("\n# ", start + 10)]
    head, _, leaf = name.partition(".")
    for line in section.splitlines():
        if f"`{head}." in line and leaf in line:
            return line
    return ""


def test_nothing_is_emitted_behind_the_contract():
    """코드가 내는 것은 카탈로그에 있어야 한다.

    `docking.*` 11 종이 그랬다. 계약만 읽는 소비자는 도킹이 어디까지 갔는지,
    왜 실패했는지 알 방법이 없었고, 문서화되지 않은 이벤트는 §1 의 폐기 정책
    바깥에 있어 언제 사라져도 아무도 약속을 깨지 않은 것이 된다.
    """
    undocumented = emitted() - set(catalogue())

    assert not undocumented, (
        "코드가 내는데 카탈로그에 없다: " + ", ".join(sorted(undocumented))
    )


@pytest.mark.parametrize("event", sorted(
    name for name in emitted() if name.startswith("docking.")))
def test_each_docking_event_carries_a_documented_payload(event):
    """payload 열이 비어 있으면 문서화한 것이 아니다."""
    note = _row_note(event)

    assert "{" in note, f"{event}: payload 가 적혀 있지 않다"


def test_the_fleet_rows_are_excluded_by_their_sender_column():
    """`mission.*` 는 Fleet 이 낸다. 하드코딩한 예외 목록이 아니라 표가 정한다."""
    senders = catalogue()

    assert senders["mission.assigned"] == "Fleet"
    assert "mission.assigned" not in robot_side()
    assert "safety.estop" in robot_side()
