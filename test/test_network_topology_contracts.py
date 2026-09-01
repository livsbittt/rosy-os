"""Cross-document contracts for the network topology decision (ADR D-26).

ADR D-26 supersedes D-19: the robot supports two operating network modes,
``SITE_STA`` (default) and ``RELAY_AP_STA`` (per-device opt-in). Three
documents have to agree on that — the ADR log, the CORE SRS and the ROSY OS
v1 image/release design. They drifted apart once already (D-19 declared
AP+STA the standard topology while the v1 design excluded relay from scope),
so the agreement is pinned here rather than left to review.
"""

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "docs" / "reference" / "ROSY ADR Log.md"
SRS = ROOT / "docs" / "spec" / "ROSY CORE SRS.md"
DESIGN = ROOT / "docs" / "plans" / "2026-09-01-rosy-os-v1-image-release-design.md"

CONTRACT_DOCS = (ADR, SRS, DESIGN)

SITE_STA = "SITE_STA"
RELAY = "RELAY_AP_STA"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def adr() -> str:
    return _text(ADR)


@pytest.fixture(scope="module")
def srs() -> str:
    return _text(SRS)


@pytest.fixture(scope="module")
def design() -> str:
    return _text(DESIGN)


def test_contract_documents_exist():
    for path in CONTRACT_DOCS:
        assert path.is_file(), f"missing contract document: {path.relative_to(ROOT)}"


# --- ADR governance -------------------------------------------------------


def test_d19_is_superseded_not_edited_in_place(adr):
    """The ADR log's own rule: supersede, never rewrite a decision."""
    assert "## D-19 접속 토폴로지: 로봇 WiFi 릴레이(AP+STA) 지원" in adr, (
        "D-19 must survive verbatim as the historical record"
    )
    assert "**Status:** Superseded by D-26" in adr
    assert "| D-19 | 접속 토폴로지: 로봇 WiFi 릴레이(AP+STA) 지원 | Superseded by D-26 |" in adr


def test_d26_exists_and_replaces_d19(adr):
    assert "## D-26" in adr
    d26 = adr.split("## D-26", 1)[1]
    assert "D-19 대체" in d26
    assert SITE_STA in d26 and RELAY in d26


def test_adr_index_lists_every_decision_section(adr):
    """The index table went stale at D-22 while D-23..D-25 existed in the body."""
    import re

    body_ids = set(re.findall(r"^## (D-\d+) ", adr, flags=re.MULTILINE))
    index_ids = set(re.findall(r"^\| (D-\d+) \|", adr, flags=re.MULTILINE))
    missing = sorted(body_ids - index_ids, key=lambda s: int(s.split("-")[1]))
    assert not missing, f"ADR sections absent from the index table: {missing}"


# --- the decision itself --------------------------------------------------


def test_relay_is_in_v1_scope_everywhere():
    """No document may still defer the relay to a follow-on capability."""
    deferrals = (
        "상시 AP+STA 릴레이는 v1 기본이 아니며 후속 Capability로 보류한다",
        "상시 AP+STA relay와 도메인별 응용 기능은 이 완료 정의에",
        "v1 기본 요구에서 제외한다",
    )
    for path in CONTRACT_DOCS:
        text = _text(path)
        for phrase in deferrals:
            assert phrase not in text, (
                f"{path.relative_to(ROOT)} still defers the relay out of v1: {phrase!r}"
            )


def test_both_modes_named_in_every_contract_document():
    for path in CONTRACT_DOCS:
        text = _text(path)
        assert SITE_STA in text, f"{path.relative_to(ROOT)} does not name {SITE_STA}"
        assert RELAY in text, f"{path.relative_to(ROOT)} does not name {RELAY}"


def test_site_sta_is_declared_the_default(adr, srs, design):
    assert "`SITE_STA` — **기본값.**" in adr
    assert "기본값은 `SITE_STA`이며 릴레이는 장비별로 명시적으로 켠다" in srs
    assert "설정이 없으면 `SITE_STA`로 기동한다" in srs
    assert "운용 네트워크 모드는 `SITE_STA`와 `RELAY_AP_STA` 두 가지이며 기본은 `SITE_STA`다" in design


def test_relay_is_declared_opt_in(adr, srs, design):
    assert "**장비별 옵트인.**" in adr
    assert "장비별 옵트인" in srs
    assert "장비별 옵트인으로 한다" in design


def test_both_modes_share_the_first_boot_provisioning_ap(adr, srs, design):
    assert "동일한 첫 부팅 설정 AP" in adr
    assert "두 모드 모두 동일한 첫 부팅 설정 AP로 프로비저닝된다" in srs
    assert "두 운용\n모드 어느 쪽으로 갈지는 프로비저닝 단계에서 선택" in design


def test_provisioning_ap_is_separate_from_the_operating_relay_ap(srs, design):
    """The setup AP and the relay AP are different profiles with different lifetimes."""
    assert "### NET-005" in srs
    net005 = srs.split("### NET-005", 1)[1]
    assert "설정 AP의 자격정보를 재사용해서는 안 된다" in net005
    assert "설정 AP의 자격정보를 운용 AP가 재사용하지 않는다" in design


# --- downstream consistency ----------------------------------------------


def test_srs_net_requirements_cover_both_modes(srs):
    section = srs.split("## 3.1 ", 1)[1].split("### IDN-003", 1)[0]
    for req in ("NET-001", "NET-002", "NET-003", "NET-004", "NET-005"):
        assert f"### {req}" in section, f"{req} missing from SRS 3.1"

    # NET-003 must state where "local stays up" holds in each mode, because the
    # two modes fail differently: relay keeps its own subnet, STA depends on the
    # site router not isolating clients.
    net003 = section.split("### NET-003", 1)[1].split("### NET-004", 1)[0]
    assert "client isolation" in net003
    assert "로봇 AP 서브넷" in net003


def test_design_state_machine_offers_both_operating_modes(design):
    machine = design.split("### 8.1 네트워크 모드", 1)[1].split("### 8.2", 1)[0]
    assert "-> SITE_STA" in machine
    assert "-> RELAY_AP_STA" in machine
    assert "PROVISIONING_AP" in machine


def test_dashboard_network_card_shows_the_relay_mode(design):
    """A mode the runtime can enter but the dashboard cannot name is a blind spot."""
    card = design.split("### 10.2 네트워크", 1)[1].split("### 10.3", 1)[0]
    for mode in ("PROVISIONING_AP", SITE_STA, RELAY, "RECOVERY_AP"):
        assert mode in card, f"dashboard network card omits {mode}"


def test_design_points_at_the_superseding_adr(design):
    assert "ADR D-26" in design
    assert "D-19를 D-26으로 대체" in design
