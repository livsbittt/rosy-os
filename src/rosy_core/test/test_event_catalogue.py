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
from typing import Optional

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


def _names_in(node: ast.AST) -> Optional[list[str]]:
    """이벤트 **이름 자리**의 문자열. 정적으로 못 읽으면 `None`.

    `publish("config.changed", data={"key": "safety.limits"})` 에서
    `safety.limits` 는 설정 키이지 이벤트가 아니다. 이름 자리만 보는 것으로
    그런 것이 걸러진다.

    `None` 과 빈 목록은 다르다. 빈 목록은 "이름이 아니다"(예: 첫 인자가 숫자),
    `None` 은 "이름 자리인데 읽지 못했다"(f-string, 모듈 상수, 변수) 이고 —
    그것은 조용히 넘길 것이 아니라 실패시킬 것이다. 읽지 못한 것을 통과시키는
    가드는 통과시키는 법을 하나 더 배운 것뿐이다.
    """
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return [node.value] if _EVENT_NAME.fullmatch(node.value) else []
        return []
    if isinstance(node, ast.IfExp):
        # self._emit("docking.charging" if confirmed else "docking.charge_lost", ...)
        left, right = _names_in(node.body), _names_in(node.orelse)
        if left is None or right is None:
            return None
        return left + right
    return None


def severity_spellings(tree: ast.AST) -> frozenset[str]:
    """이 모듈에서 `Severity` 열거형을 부르는 이름들.

    접미사로 넘겨짚지 않는다. `import … as Level` 한 줄이면 접미사 규칙은
    그 발행 지점을 **조용히** 놓치고, 접미사에 걸리는 아무 변수(`sev`,
    `thresholds.severity`)는 심각도가 아닌데 심각도로 읽힌다. 그 모듈이 실제로
    무엇을 import 했는지가 답이고, 소스는 이미 손에 있다.
    """
    names = {"Severity"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name.rsplit(".", 1)[-1] == "Severity":
                    names.add(alias.asname or "Severity")
    return frozenset(names)


def _severity_written_at(node: ast.AST,
                         spellings: frozenset[str] = frozenset({"Severity"})
                         ) -> Optional[str]:
    """이 노드가 심각도인가. `"warning"` 이거나 `Severity.WARNING` 이거나.

    소유자를 확인하는 것이 중요하다. 열거형이면 무엇이든 받으면
    `BatteryLevel.CRITICAL` 이 심각도로 읽히고, `if level not in
    (BatteryLevel.WARNING, BatteryLevel.CRITICAL, BatteryLevel.DEEP)` 라는
    평범한 멤버십 검사가 발행 튜플로 잡힌다.
    """
    if isinstance(node, ast.Constant) and node.value in _SEVERITIES:
        return node.value
    if isinstance(node, ast.Attribute) and node.attr.lower() in _SEVERITIES:
        owner = node.value
        # `Severity.X` 도 `schemas.Severity.X` 도 소유자 끝이 그 이름이다.
        spelled = getattr(owner, "attr", None) or getattr(owner, "id", "")
        if spelled in spellings:
            return node.attr.lower()
    return None


def _severity_of(node: Optional[ast.AST], spellings: frozenset[str]) -> Optional[str]:
    """심각도 자리의 값. 비어 있으면 `EventBus.publish` 의 기본값인 info 다.

    자리가 **비어 있는 것** 과 자리에 무언가 있는데 **읽지 못한 것** 은 다르다.
    앞은 기본값 info 가 맞고(43 개 중 16 개가 그렇다), 뒤는 조용히 info 로
    적어 넣으면 문서도 info 라고 적혀 있을 때 그 어긋남이 영영 안 보인다.
    읽지 못한 것은 `None` 으로 돌려 실패시킨다.

    **자리를 정해 읽는다.** 인자를 훑어 심각도처럼 생긴 것을 집으면
    `publish("x.y", source="error", …)` 의 `source` 가 심각도로 읽힌다.
    """
    if node is None:
        return "info"
    return _severity_written_at(node, spellings)


def _looks_like_an_emit_tuple(elts: list[ast.AST], spellings: frozenset[str]) -> bool:
    """`(type, severity, data)` 인가, 아니면 그냥 문자열 두 개짜리 튜플인가.

    모양만 보면 `("config.yaml", "path")` 나 `if x in ("mission.assigned", …)`
    같은 평범한 튜플이 이벤트로 잡힌다. 심각도나 payload 가 함께 있어야
    발행 자리다.
    """
    return any(isinstance(node, ast.Dict)
               or _severity_written_at(node, spellings) is not None
               for node in elts[1:])


#: ROS 퍼블리셔 변수의 이름 규약. 이 패키지는 예외 없이 이렇게 짓는다.
_ROS_PUBLISHER_SUFFIXES = ("_pub", "_publisher")


def _is_event_bus(func: ast.AST) -> bool:
    """`self._events.publish(...)` 인가 `self.cmd_vel_pub.publish(msg)` 인가.

    ROS 퍼블리셔도 `publish` 다. 이름 자리에 `Twist()` 가 앉아 있으니 "이름을
    못 읽었다"로 잡혀 가드가 영원히 빨개진다.

    **버스를 허용 목록으로 고르지 않는다.** `self._events`·`svc.events` 만
    통과시키면 `events.publish(...)`(모듈 전역·지역 이름)나 `self.bus.publish(...)`
    는 발행 자리로 세어지지도 않고 **조용히** 빠진다 — 가드가 눈을 감는 쪽으로
    틀리는 것이다. 그래서 반대로 적는다: `publish` 는 전부 발행 자리이고,
    ROS 퍼블리셔 이름 규약(`*_pub`)에 맞는 것만 뺀다. 규약을 벗어난 퍼블리셔가
    생기면 가드가 빨개지고, 그것은 이름을 고치거나 여기를 고치라는 뜻이다 —
    어느 쪽이든 사람이 보게 된다.
    """
    if not isinstance(func, ast.Attribute):
        return False
    owner = func.value
    name = owner.attr if isinstance(owner, ast.Attribute) else getattr(owner, "id", "")
    return not name.endswith(_ROS_PUBLISHER_SUFFIXES)


def _publishes(node: ast.AST) -> bool:
    """이 함수 몸통에 발행 호출이 있는가.

    ROS 퍼블리셔는 세지 않는다. `self.cmd_vel_pub.publish(msg)` 하나가 함수를
    중계로 승격시키면, 중계에만 주는 면제가 그 함수에 딸려 들어간다.
    """
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        called = getattr(inner.func, "attr", "") or getattr(inner.func, "id", "")
        if called == "_emit" or (called == "publish" and _is_event_bus(inner.func)):
            return True
    return False


#: 새 스코프. 여기 안쪽의 대입은 바깥 이름을 다시 묶는 것이 아니다.
_NESTED_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
                  ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _rebound_in(node: ast.AST) -> set[str]:
    """이 몸통에서 **다시 묶이는** 이름들.

    `def _emit(type_, …): type_ = compute(); self._events.publish(type_, …)` 는
    더 이상 중계가 아니다 — 호출 자리에서 읽은 이름과 발행되는 이름이 다르다.

    대입문만 보면 부족하다. `type_, extra = f()`, `(type_ := f())`,
    `for type_ in xs`, `with o() as type_`, `except E as type_`,
    `import os as type_`, `case [type_]`, `global type_`, 그리고 `def type_():`
    까지 전부 같은 일을 한다. 열두 가지가 조용히 빠져 있었고, 그렇게 되면 이
    검사는 장식이다 — 면제를 안전하게 만들라고 있는 것이기 때문이다.

    중첩 스코프에는 들어가지 않는다. 그 안의 대입은 다른 이름이고, 세면
    멀쩡한 중계가 거짓으로 빨개진다.
    """
    names: set[str] = set()

    def walk(parent: ast.AST) -> None:
        for child in ast.iter_child_nodes(parent):
            if isinstance(child, _NESTED_SCOPES):
                # 이름 자체는 여기서 묶인다. 몸통은 다른 스코프다.
                names.add(getattr(child, "name", ""))
                continue
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                names.add(child.id)
            elif isinstance(child, ast.ExceptHandler) and child.name:
                names.add(child.name)
            elif isinstance(child, ast.alias) and child.asname:
                names.add(child.asname)
            elif isinstance(child, (ast.MatchAs, ast.MatchStar)) and child.name:
                names.add(child.name)
            elif isinstance(child, (ast.Global, ast.Nonlocal)):
                names.update(child.names)
            walk(child)

    walk(node)
    names.discard("")
    return names


class _Relay:
    """중계 함수 안에서의 상태.

    `params` 는 그 함수가 받은 이름들(어떤 이터러블이 중계 대상인지 알기 위해),
    `blessed` 는 지금 이 자리에서 면제되는 이름들이다.
    """

    __slots__ = ("params", "blessed")

    def __init__(self, params: frozenset[str], blessed: frozenset[str]) -> None:
        self.params = params
        self.blessed = blessed


def _relay_bindings(node: ast.AST, inherited: Optional[_Relay]) -> Optional[_Relay]:
    """이 노드가 **자기 안쪽에** 새로 걸어 주는 중계 이름들.

    `None` 은 "중계 함수 안이 아니다" 이다.

    중계를 봐주는 근거는 "그 이름은 다른 자리에서 이미 읽혔다"이지 "그렇게
    생긴 변수는 봐준다"가 아니다. 그래서 세 겹으로 좁힌다.

    **범위로**: 걸어 주는 것은 그 이름을 묶은 구문의 안쪽뿐이다. 파일 전체에
    뿌리면 `name`·`key`·`value`·`source`·`component` 처럼 흔한 식별자가 통째로
    면제된다.

    **자리로**: 중계 함수(`_emit…` 이면서 실제로 발행하는 것) 안에서만 건다.
    그리고 파라미터를 봐주는 것은 이름이 정확히 `_emit` 일 때뿐이다 — 추출기가
    이름을 읽는 호출은 그것 하나이므로, `_emit_health(component)` 의 파라미터를
    봐주면 그 이름은 **어디에서도** 읽히지 않은 채 지나간다.

    **대상으로**: for 튜플 언팩은 **중계가 받은 것을 푸는 자리**일 때만 건다.
    `for … in <파라미터>` 여야 한다. 이것이 없으면 `_emit_all` 안에 관계없는
    루프를 하나 더 놓는 것으로 그물이 다시 뚫린다 — 리뷰가 실제
    `power/manager.py` 의 `_emit_all` 에 몇 줄 붙여 659 개 테스트를 전부
    초록으로 통과시킨 것이 그것이다.

    `self` 는 뺀다. 중계가 아닌 함수는 새 스코프이므로 바깥에서 걸린 것도
    함께 끊는다.
    """
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if not (node.name.startswith("_emit") and _publishes(node)):
            return None
        params = frozenset(arg.arg for arg in node.args.args if arg.arg != "self")
        if node.name != "_emit":
            # 중계 안이긴 하나 스스로 걸어 주는 것은 없다. `_emit_all` 처럼
            # 튜플을 푸는 중계는 아래 for 규칙으로 성립한다 — 그 이름들은
            # 튜플 리터럴 쪽에서 이미 읽혔다.
            return _Relay(params, frozenset())
        return _Relay(params, frozenset(params - _rebound_in(node)))
    if (inherited is not None
            and isinstance(node, ast.For) and isinstance(node.target, ast.Tuple)
            and isinstance(node.iter, ast.Name) and node.iter.id in inherited.params):
        unpacked = {elt.id for elt in node.target.elts if isinstance(elt, ast.Name)}
        # 다시 묶이는지는 **몸통에서** 본다. for 의 target 자체는 묶는 자리이지
        # 다시 묶는 자리가 아니다 — 거기까지 세면 자기 자신을 빼게 된다.
        rebound: set[str] = set()
        for statement in list(node.body) + list(node.orelse):
            rebound |= _rebound_in(statement)
        return _Relay(inherited.params,
                      inherited.blessed | frozenset(unpacked - rebound))
    return inherited


def relay_functions() -> set[tuple[str, str]]:
    """중계 면제를 받는 함수들. 이 목록이 늘어나면 사람이 봐야 한다."""
    found: set[tuple[str, str]] = set()
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name.startswith("_emit") and _publishes(node)):
                found.add((path.relative_to(PACKAGE).as_posix(), node.name))
    return found


#: 이벤트 이름과 모양이 같은 파일 이름들 (`app.js`, `docks.json`, `audit.jsonl`).
_FILE_SUFFIXES = {"js", "css", "html", "json", "jsonl", "yaml", "yml", "md", "sh", "py"}

#: 첫 인자가 "점 찍힌 이름"인데 이벤트가 아닌 호출들. capability 경로(CAP-001)와
#: Host Agent RPC 메서드가 그렇다 — 목록이 아니라 **자리** 로 걸러진다.
_NAMESPACED_FIRST_ARG = {"require", "supports", "request"}


def _literals_with_another_job(tree: ast.AST) -> set[str]:
    """이벤트가 아닌 것이 이미 분명한 자리에 놓인 문자열들."""
    spoken_for: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and node.args):
            continue
        func = node.func
        called = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        first = node.args[0]
        if called in _NAMESPACED_FIRST_ARG and isinstance(first, ast.Constant):
            if isinstance(first.value, str):
                spoken_for.add(first.value)
        for keyword in node.keywords:
            # `_authorize(websocket, capability="swarm.lead")` — 자리는 같고
            # 이름만 키워드로 적힌 것.
            if keyword.arg == "capability" and isinstance(keyword.value, ast.Constant):
                if isinstance(keyword.value.value, str):
                    spoken_for.add(keyword.value.value)
    return spoken_for


def emit_sites() -> tuple[list[Emit], list[str]]:
    """발행 지점들과, **이름을 읽지 못한 자리들**.

    두 번째 목록이 비어 있지 않으면 가드는 그만큼 눈을 감고 있는 것이다.
    """
    sites: list[Emit] = []
    unresolved: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        # 패키지에 `manager.py` 가 여섯 개다. 파일 이름만 적으면 실패 메시지가
        # 읽는 사람을 엉뚜한 파일로 보낸다.
        found, blind = scan(path.read_text(encoding="utf-8"),
                            path.relative_to(PACKAGE).as_posix())
        sites.extend(found)
        unresolved.extend(blind)
    return sites, unresolved


def scan(source: str, origin: str = "<test>") -> tuple[list[Emit], list[str]]:
    """소스 하나에서 발행 지점을 읽는다.

    파일이 아니라 문자열을 받는 것이 요점이다 — 추출기가 무엇을 잡고 무엇을
    놓치는지를 합성 소스로 직접 물을 수 있어야, "빠져나갈 수 없다"가 주장이
    아니라 테스트가 된다.
    """
    sites: list[Emit] = []
    unresolved: list[str] = []
    tree = ast.parse(source)
    spellings = severity_spellings(tree)

    def descend(node: ast.AST, inherited: Optional[_Relay]) -> None:
        relayed = _relay_bindings(node, inherited)
        read(node, relayed)
        for child in ast.iter_child_nodes(node):
            descend(child, relayed)

    def read(node: ast.AST, relayed: Optional[_Relay]) -> None:
        first: ast.AST | None = None
        severity_node: ast.AST | None = None
        payloads: list[ast.AST] = []
        is_call = False
        if isinstance(node, ast.Call):
            func = node.func
            called = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if called == "_emit" or (called == "publish" and _is_event_bus(func)):
                is_call = True
                keywords = {k.arg: k.value for k in node.keywords}
                first = node.args[0] if node.args else keywords.get("type_") or keywords.get("type")
                severity_node = (node.args[1] if len(node.args) > 1
                                 else keywords.get("severity"))
                payloads = list(node.args[1:]) + [k.value for k in node.keywords]
        elif (isinstance(node, ast.Tuple) and 2 <= len(node.elts) <= 3
              and _looks_like_an_emit_tuple(node.elts, spellings)):
            # 절전·배터리는 `(type, severity, data)` 튜플을 모아 두었다가
            # 한 번에 낸다 — append 로도, 리스트 리터럴로도.
            first = node.elts[0]
            severity_node = node.elts[1] if len(node.elts) > 1 else None
            payloads = list(node.elts[1:])

        if first is None and not is_call:
            return
        where = f"{origin}:{getattr(node, 'lineno', 0)}"
        if first is None:
            unresolved.append(f"{where}: 이름 인자가 없다")
            return
        names = _names_in(first)
        if names is None:
            if (relayed is not None and isinstance(first, ast.Name)
                    and first.id in relayed.blessed):
                return  # 중계 — 이름은 튜플 리터럴·호출 자리에서 이미 읽었다
            # 호출이든 튜플이든 마찬가지다. `_looks_like_an_emit_tuple` 을
            # 통과한 튜플은 이미 자기가 발행 자리라고 말한 것이므로, 그
            # 이름을 못 읽으면 그것도 눈을 감은 것이다. 이 모양은
            # `power/battery.py`·`power/manager.py` 가 실제로 쓰는 것이라, 새
            # 배터리·절전 이벤트가 가장 쉬운 길로 새는 자리였다.
            unresolved.append(f"{where}: 이름을 정적으로 읽을 수 없다")
            return
        if not names:
            return

        severity = _severity_of(severity_node, spellings)
        if severity is None:
            unresolved.append(f"{where}: 심각도를 정적으로 읽을 수 없다")
            return
        payload = next((a for a in payloads if isinstance(a, ast.Dict)), None)
        keys: frozenset[str] | None = None
        if payload is not None:
            literal = [k.value for k in payload.keys
                       if isinstance(k, ast.Constant) and isinstance(k.value, str)]
            if len(literal) == len(payload.keys):
                keys = frozenset(literal)
        sites.extend(Emit(name, severity, keys, where) for name in names)

    descend(tree, None)
    return sites, unresolved


def emitted() -> list[Emit]:
    return emit_sites()[0]


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
    def severities(self) -> set[str]:
        """한 칸에 여러 값이 적힌 행이 있다 (`info/error/info`)."""
        return {part.strip() for part in re.split(r"[/,]", self.severity) if part.strip()}

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
    names = {site.name for site in emitted()}
    promised = {name for name, row in catalogue().items()
                if row.robot_sent and not row.unimplemented}

    assert not promised - names, (
        "카탈로그가 약속하는데 코드가 내지 않는다: " + ", ".join(sorted(promised - names))
    )


def test_nothing_is_emitted_behind_the_contract():
    """코드가 내는 것은 카탈로그에 있어야 한다.

    `docking.*` 11 종과 `battery.deep` 이 그랬다. 문서화되지 않은 이벤트는 §1 의
    폐기 정책 바깥에 있어, 언제 사라져도 아무도 약속을 깬 것이 아니게 된다.
    """
    documented = set(catalogue())
    undocumented = sorted({site.name for site in emitted()} - documented)

    assert not undocumented, "코드가 내는데 카탈로그에 없다: " + ", ".join(undocumented)


def test_every_documented_payload_key_is_one_the_code_sends():
    """`{}` 안에 적힌 키는 실제로 실려야 한다.

    `nav.stuck` 은 `{timeout_ms}` 로 적혀 있었고 코드는 `timeout_s` 를 보냈다.
    계약대로 읽은 소비자는 KeyError 를 받는다.
    """
    sent: dict[str, set[str]] = {}
    for site in emitted():
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
    for site in emitted():
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
    for site in emitted():
        row = documented.get(site.name)
        if row is None:
            continue
        # 부분 문자열이 아니라 값이다. `in` 으로 두면 한 칸에 여러 값이 적히는
        # 순간(Fleet 행들이 이미 그렇다) 검사가 합집합이 되어 아무 값이나 받는다.
        if site.severity not in row.severities:
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
        site.name for site in emitted()
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


def test_no_emit_site_hides_its_name_from_the_guard():
    """이름을 정적으로 못 읽는 발행 자리가 있으면 가드는 그만큼 눈을 감는다.

    `publish(type_=…)`, `publish(f"docking.{stage}")`, `publish(EVT)` 는 모두
    조용히 통과했다. 통과시키는 대신 여기서 실패한다 — 새 발행 자리는 이름을
    리터럴로 적거나, 이 검사를 고치고 왜 그런지 적어야 한다.
    """
    _sites, unresolved = emit_sites()

    assert not unresolved, "\n".join(unresolved)


def test_a_literal_that_looks_like_an_event_is_either_emitted_or_declared():
    """발행 자리를 우회한 이름을 잡는 두 번째 그물.

    래퍼 함수를 거치면 발행 자리 추출은 놓친다 — 그래도 문자열은 소스에 남는다.
    이벤트처럼 생긴 문자열은 실제 발행 이름이거나, 아래 목록에 이유와 함께
    있어야 한다.

    목록이 실제 이벤트를 숨기는 것이 지난 판본의 실패였다. 그래서 목록과 발행
    이름이 겹치면 그것 자체가 실패다 — 숨기려면 먼저 그 교집합을 통과해야 한다.
    """
    #: 이벤트처럼 생겼지만 이벤트가 아닌 것. 각각 그 자리에서 무엇인지 적는다.
    #: **목록이 아니라 자리로** 거르는 것이 원칙이다 — 아래 셋은 자리로 설명되지
    #: 않아서 남은 것들이고, 이 목록이 길어지면 그건 새 *자리* 를 배워야 한다는
    #: 신호이지 한 줄 더 적으라는 신호가 아니다.
    not_events = {
        "safety.limits": "config.changed 의 key 값",
        "robot.identity": "config.changed 의 key 값",
        "auth.tokens": "config.changed 의 key 값",
    }
    names = {site.name for site in emitted()}

    overlap = sorted(set(not_events) & names)
    assert not overlap, (
        "이 목록이 실제 발행 이벤트를 숨기고 있다: " + ", ".join(overlap))

    unclassified: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        spoken_for = _literals_with_another_job(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            value = node.value
            if not _EVENT_NAME.fullmatch(value) or value in names or value in not_events:
                continue
            if value in spoken_for or value.rpartition(".")[2] in _FILE_SUFFIXES:
                continue
            unclassified.append(f"{path.name}:{node.lineno}: {value}")

    assert not unclassified, (
        "이벤트처럼 생긴 문자열인데 발행 이름도 아니고 목록에도 없다:\n"
        + "\n".join(unclassified))


def test_the_extractor_reads_the_shapes_this_package_actually_uses():
    """추출기가 조용히 아무것도 못 찾으면 위의 모든 검사가 공허해진다."""
    sites = emitted()
    names = {site.name for site in sites}

    # 실제 43 개다. `>= 30` 으로 두면 13 개가 조용히 사라져도 통과한다.
    assert len(names) >= 40, f"only found {len(names)}"
    # 직접 호출, 튜플 수집, 조건식 이름 — 세 가지 모양이 모두 잡혀야 한다.
    assert "nav.started" in names            # publish("...", data={...})
    assert "power.mode_changed" in names     # pending.append((...))
    assert "docking.charge_lost" in names    # "a" if cond else "b"
    assert any(site.keys for site in sites if site.name == "safety.watchdog")


@pytest.mark.parametrize("event", ["battery.deep", "safety.watchdog", "docking.failed"])
def test_the_events_this_change_was_about_are_covered(event):
    """회귀 방지: 이 셋이 각각 이 파일이 존재하는 이유다."""
    assert event in catalogue()
    assert event in {site.name for site in emitted()}


# --- 추출기 자신에 대한 검사 ------------------------------------------------
#
# 위의 검사들은 전부 "추출기가 발행 지점을 다 찾는다"에 기대고 있다. 그
# 전제가 틀리면 전부 공허해지고, 틀렸다는 사실은 조용하다. 그래서 합성
# 소스로 직접 묻는다.


def _names_and_blind(source: str) -> tuple[set[str], list[str]]:
    sites, unresolved = scan(source)
    return {site.name for site in sites}, unresolved


@pytest.mark.parametrize("source,expected", [
    ('self._events.publish("nav.started", data={"goal": 1})', "nav.started"),
    ('svc.events.publish("nav.started", data={"goal": 1})', "nav.started"),
    ('self.core.events.publish("nav.started", data={"goal": 1})', "nav.started"),
    # 허용 목록이 아니라 제외 목록이므로, 버스를 어디에 담아도 잡힌다.
    ('events.publish("nav.started", data={"goal": 1})', "nav.started"),
    ('self.bus.publish("nav.started", data={"goal": 1})', "nav.started"),
    ('self._emit("nav.started", "info", {"goal": 1})', "nav.started"),
    # 이름을 키워드로 적어도 자리는 같다.
    ('self._events.publish(type_="nav.started", data={"goal": 1})', "nav.started"),
    # 튜플로 모아 두었다가 내는 것.
    ('pending.append(("nav.started", "info", {"goal": 1}))', "nav.started"),
])
def test_the_shapes_that_publish_are_all_seen(source, expected):
    names, blind = _names_and_blind(source)

    assert expected in names, f"{source} 를 놓쳤다"
    assert not blind


@pytest.mark.parametrize("source", [
    'self._events.publish(f"docking.{stage}", data={})',      # f-string
    'self._events.publish(EVENT_NAME, data={})',              # 모듈 상수
    'self._events.publish(name, data={})',                    # 지역 변수
    'self._events.publish(NAMES[0], data={})',                # 첨자
    'self._events.publish("nav." + suffix, data={})',         # 이어붙이기
    'self._events.publish(data={})',                          # 이름 자리가 없다
])
def test_a_name_the_guard_cannot_read_is_reported_not_skipped(source):
    """조용히 넘기면 가드는 통과시키는 법을 하나 더 배운 것뿐이다."""
    names, blind = _names_and_blind(source)

    assert not names
    assert blind, f"{source} 가 조용히 지나갔다"


def test_a_ros_publisher_is_not_mistaken_for_the_bus():
    names, blind = _names_and_blind("self.cmd_vel_pub.publish(msg)")

    assert not names and not blind


def test_a_publisher_that_breaks_the_naming_convention_fails_loudly():
    """모르는 모양은 통과가 아니라 실패다.

    `_pub` 규약을 벗어난 ROS 퍼블리셔가 생기면 여기가 빨개진다 — 이름을
    고치거나 규약을 고치라는 뜻이고, 어느 쪽이든 사람이 보게 된다. 반대로
    적었다면(버스만 허용) 그 자리는 조용히 사라졌을 것이다.
    """
    _names, blind = _names_and_blind("self.wheels.publish(msg)")

    assert blind


@pytest.mark.parametrize("label,source", [
    # 중계는 이름이 **다른 자리에서 읽히기 때문에** 봐주는 것이다. 그 근거가
    # 없는 이름은 모양이 닮았다고 봐주지 않는다.
    ("평범한 지역 변수",
     "def send(self, kind):\n"
     "    self._events.publish(kind, data={})\n"),
    # 리뷰가 실제 패키지의 observability.py 에 한 줄 넣어 641 개 테스트를 전부
    # 초록으로 통과시킨 모양이다. for 튜플 언팩이라는 것만으로 봐주면
    # `component`·`name`·`key`·`value`·`source` 가 통째로 면제된다.
    ("중계 함수 밖의 for 튜플 언팩",
     "def metrics(svc):\n"
     "    for component, health in items:\n"
     "        svc.events.publish(component, severity='error', data={'health': 1})\n"),
    ("모듈 수준의 for 튜플 언팩",
     "for component, health in items:\n"
     "    svc.events.publish(component, data={})\n"),
    # `_emit` 파라미터는 그 함수 **안에서만** 중계다.
    ("_emit 파라미터를 다른 함수에서 쓴 것",
     "def _emit(self, type_, severity, data):\n"
     "    self._events.publish(type_, severity=severity, data=data)\n"
     "def elsewhere(self):\n"
     "    self._events.publish(type_, data={})\n"),
    # 이름만 `_emit…` 인 헬퍼는 중계가 아니다.
    ("발행하지 않는 _emit… 헬퍼",
     "def _emit_label(self, type_):\n"
     "    return type_.upper()\n"
     "def send(self, type_):\n"
     "    self._events.publish(type_, data={})\n"),
    # **발행하는** `_emit…` 헬퍼도 마찬가지다. 파라미터를 봐주는 근거는 그
    # 이름이 `_emit(…)` 호출 자리에서 읽힌다는 것인데, 추출기가 읽는 호출
    # 이름은 정확히 `_emit` 뿐이다. 리뷰가 실제 패키지에서 이름 한 단어를
    # 늘리는 것만으로 같은 구멍을 다시 통과했다.
    ("발행하는 _emit… 래퍼 함수",
     "def _emit_component_health(component):\n"
     "    svc.events.publish(component, severity='error', data={'health': 1})\n"
     "def metrics(svc):\n"
     "    for component, health in items:\n"
     "        _emit_component_health(component)\n"),
    ("발행하는 _emit… 메서드",
     "class S:\n"
     "    def _emit_health(self, component):\n"
     "        self._events.publish(component, data={})\n"),
    # ROS 퍼블리셔는 함수를 중계로 승격시키지 않는다.
    ("ROS 퍼블리셔로 중계 행세를 한 것",
     "def _emit_wheels(self, kind):\n"
     "    self.cmd_vel_pub.publish(msg)\n"
     "    self._events.publish(kind, data={})\n"),
    # for 튜플 언팩은 **중계가 받은 것을 푸는 자리**일 때만 봐준다. 관계없는
    # 이터러블 위의 루프는 그냥 루프다 — 리뷰가 실제 `power/manager.py` 의
    # `_emit_all` 에 이런 루프를 하나 더 붙여 659 개 테스트를 전부 초록으로
    # 통과시켰다.
    ("중계 안이지만 관계없는 이터러블 위의 for",
     "def _emit(self, type_, severity, data):\n"
     "    for name, value in EXTRA:\n"
     "        self._events.publish(name, data={})\n"),
    ("_emit_all 에 덧붙인 두 번째 루프",
     "def _emit_all(self, pending):\n"
     "    for type_, severity, data in pending:\n"
     "        self._events.publish(type_, severity=severity, data=data)\n"
     "    for component, health in self._component_health().items():\n"
     "        self._events.publish(component, severity='error', data={'h': health})\n"),
    # 다시 대입하면 호출 자리에서 읽은 이름과 발행되는 이름이 다르다.
    ("_emit 안에서 파라미터를 다시 대입한 것",
     "def _emit(self, type_, severity, data):\n"
     "    type_ = compute()\n"
     "    self._events.publish(type_, severity=severity, data=data)\n"),
])
def test_the_relay_allowance_does_not_cover_a_name_read_nowhere_else(label, source):
    _names, blind = _names_and_blind(source)

    assert blind, f"{label} 이(가) 조용히 지나갔다"


@pytest.mark.parametrize("imports,spelling", [
    ("", "'critical'"),
    ("from rosy_core.protocol.schemas import Severity\n", "Severity.CRITICAL"),
    ("from rosy_core.protocol import schemas\n", "schemas.Severity.CRITICAL"),
    # 접미사로 넘겨짚으면 이 한 줄이 그 발행 지점을 조용히 놓친다.
    ("from rosy_core.protocol.schemas import Severity as Sev\n", "Sev.CRITICAL"),
    ("from rosy_core.protocol.schemas import Severity as Level\n", "Level.CRITICAL"),
])
def test_the_severity_is_read_however_the_module_spells_it(imports, spelling):
    """그 모듈이 실제로 무엇을 import 했는지가 답이다.

    철자 규칙(`…sev` 로 끝나면 심각도)은 두 방향으로 틀린다: `as Level` 을
    놓치고, `thresholds.severity` 같은 것을 심각도로 읽는다.
    """
    sites, blind = scan(f"{imports}pending.append(('battery.deep', {spelling}, data))\n")

    assert [(site.name, site.severity) for site in sites] == [("battery.deep", "critical")]
    assert not blind


def test_an_enum_this_module_never_imported_is_not_a_severity():
    """`Level.CRITICAL` 이 심각도가 아니면 이것은 발행 튜플도 아니다."""
    names, blind = _names_and_blind("pending.append(('battery.deep', Level.CRITICAL, data))\n")

    assert not names and not blind


def test_a_severity_argument_that_cannot_be_read_is_reported_not_defaulted():
    """조용히 info 로 적어 넣으면, 문서도 info 라고 적혀 있을 때 그 어긋남이
    영영 보이지 않는다."""
    _names, blind = _names_and_blind(
        'self._events.publish("nav.started", severity=level, data={})\n')

    assert blind


def test_an_enum_membership_test_is_not_an_emit_tuple():
    """`BatteryLevel.CRITICAL` 은 심각도가 아니다.

    열거형이면 무엇이든 심각도로 읽으면 `if level not in (BatteryLevel.WARNING,
    BatteryLevel.CRITICAL, BatteryLevel.DEEP)` 이 발행 자리로 잡혀, 가드가
    멀쩡한 코드를 두고 거짓으로 빨개진다.
    """
    names, blind = _names_and_blind(
        "if level not in (BatteryLevel.WARNING, BatteryLevel.CRITICAL, "
        "BatteryLevel.DEEP):\n    pass\n")

    assert not names and not blind


def test_a_tuple_whose_name_cannot_be_read_is_reported_too():
    """호출만 보고하고 튜플은 넘기면, 절전·배터리가 실제로 쓰는 모양이 통째로
    감시 밖이다 — 새 이벤트가 가장 쉬운 길로 새는 자리였다."""
    _names, blind = _names_and_blind(
        "pending.append((kind, 'critical', {'percent': pct}))\n")

    assert blind


def test_a_relayed_name_is_read_at_the_tuple_not_at_the_relay():
    source = (
        'def _emit_all(self, pending):\n'
        '    for type_, severity, data in pending:\n'
        '        self._events.publish(type_, severity=severity, data=data)\n'
        '\n'
        'def collect(self):\n'
        '    pending.append(("battery.deep", "critical", {"percent": 3}))\n')
    names, blind = _names_and_blind(source)

    assert names == {"battery.deep"}
    assert not blind


def test_a_severity_left_to_the_default_is_read_as_info():
    """기본값에 기대는 발행 지점을 검사에서 빼면 3 분의 1 이 감시 밖이다."""
    sites, _blind = scan('self._events.publish("nav.started", data={})')

    assert [site.severity for site in sites] == ["info"]


def test_a_plain_tuple_is_not_read_as_an_emit():
    """`("config.yaml", "path")` 나 `x in ("mission.assigned", ...)` 같은 것."""
    names, blind = _names_and_blind(
        'PATHS = ("config.yaml", "rosy.yaml")\n'
        'if kind in ("mission.assigned", "mission.done"):\n'
        '    pass\n')

    assert not names and not blind


def test_a_non_severity_argument_is_not_read_as_the_severity():
    """자리를 정해 읽지 않으면 `source="error"` 가 심각도가 된다."""
    sites, _blind = scan('self._events.publish("nav.started", source="error", data={})')

    assert [site.severity for site in sites] == ["info"]


def test_the_documented_severity_is_matched_by_value_not_by_substring():
    row = Row("info", "로봇", "{}")

    assert row.severities == {"info"}
    assert Row("info/error/info", "Fleet", "{}").severities == {"info", "error"}


def test_the_set_of_functions_that_get_the_relay_exemption_is_the_one_we_reviewed():
    """면제는 좁히는 것만으로는 부족하다. **셀 수 있어야** 한다.

    중계 규칙은 "이 이름은 다른 자리에서 이미 읽혔다"를 정적으로 증명하지
    못한다 — 넓게 잡으면 구멍이고, 좁게 잡으면 진짜 중계가 빨개진다. 세 번의
    리뷰가 모두 이 면제의 어느 틈으로 들어왔다.

    그래서 면제받는 함수 목록 자체를 고정한다. 새 중계가 생기면 여기가 빨개지고
    사람이 그 하나를 본다. 이 목록은 **이벤트** 목록이 아니라 **예외** 목록이라,
    길어지는 것이 곧 위험 신호다.
    """
    assert relay_functions() == {
        ("docking/manager.py", "_emit"),
        ("safety/manager.py", "_emit"),
        ("power/battery.py", "_emit_all"),
        ("power/manager.py", "_emit_all"),
    }


def test_a_ros_publisher_does_not_make_a_function_a_relay():
    """`_publishes` 가 ROS 퍼블리셔를 세면, 그 함수 안의 튜플 발행 자리가
    조용히 사라진다 — 호출만 세는 것으로는 튜플 모양을 못 막는다."""
    _names, blind = _names_and_blind(
        "def _emit(self, type_, severity):\n"
        "    self.cmd_vel_pub.publish(msg)\n"
        "    pending.append((type_, severity, {'a': 1}))\n")

    assert blind
