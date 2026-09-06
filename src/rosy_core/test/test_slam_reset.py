"""NAV-005 `POST /api/v1/slam/reset` — the endpoint must not claim success.

It used to return `{"reset": true}` unconditionally. Two independent paths lied:
the session guard returned silently when no mapping session was open, and the
executor call sat behind a `hasattr` that `RosBridge` never satisfied because it
implements no `reset_mapping` at all. A Fleet reading CAP-001 saw `slam: true`,
called the route, got 200, and nothing happened.

CAP-003 (`docs/spec/ROSY CORE SRS.md`) requires a clear code rather than a
general failure for an unsupported command, and the docking path already uses
501 for exactly this. These tests pin both answers and, as importantly, pin that
a refused reset leaves no trace: no `slam.started`, no session state change.
"""

from __future__ import annotations

import pytest

from rosy_core.navigation.manager import NavigationError

OPERATOR = {"Authorization": "Bearer rosy-dev-operator"}


class RefusingExecutor:
    """A bridge that declares the contract member and cannot honour it.

    This is `RosBridge` today: the runtime has no slam_toolbox, so the method
    exists to fail with a code rather than to be missing and fail with 500.
    """

    def send_goal(self, spec):
        raise AssertionError("reset must not send a goal")

    def cancel_goal(self):
        raise AssertionError("reset must not cancel a goal")

    def send_initial_pose(self, x, y, yaw):
        raise AssertionError("reset must not touch localization")

    def save_map(self, name):
        raise AssertionError("reset must not save a map")

    def reset_mapping(self):
        raise NavigationError(
            "CAPABILITY_NOT_SUPPORTED",
            "slam_toolbox reset is not implemented in this runtime")


@pytest.fixture
def events(request):
    """Collect published event types so a test can assert nothing was emitted."""
    seen: list[str] = []

    def attach(services):
        services.events.subscribe(lambda event: seen.append(event.type))
        return seen

    return attach


def test_reset_without_an_executor_is_501_and_publishes_nothing(core_client, events):
    client, svc = core_client()
    svc.nav.start_mapping(source="test")
    seen = events(svc)

    response = client.post("/api/v1/slam/reset", headers=OPERATOR)

    assert response.status_code == 501
    assert response.json()["error"]["code"] == "CAPABILITY_NOT_SUPPORTED"
    assert "slam.started" not in seen


def test_reset_with_an_executor_that_cannot_reset_is_501_and_publishes_nothing(
        core_client, events):
    client, svc = core_client()
    svc.nav.executor = RefusingExecutor()
    svc.nav.start_mapping(source="test")
    seen = events(svc)

    response = client.post("/api/v1/slam/reset", headers=OPERATOR)

    assert response.status_code == 501
    assert response.json()["error"]["code"] == "CAPABILITY_NOT_SUPPORTED"
    assert "slam.started" not in seen


def test_capability_gate_still_precedes_the_executor(core_client, events):
    """The pre-existing 501 and the new one have different causes.

    An implementation that moved work above `capability.require("slam")` would
    keep this endpoint returning 501 and look correct. What separates the two is
    that the gated call must not reach the manager at all — so assert the
    absence of side effects, not the status code.
    """
    client, svc = core_client(capabilities={"slam": False})
    seen = events(svc)

    response = client.post("/api/v1/slam/reset", headers=OPERATOR)

    assert response.status_code == 501
    assert svc.nav.mapping_active is False
    assert seen == []


def test_moving_goal_still_refuses_while_a_mapping_session_is_open(core_client):
    """SWM-001's guard is the neighbour of the code Step 2 rewrote.

    `moving_goal()` reads `mapping_active` too. Pinned here so a change to the
    mapping session's error handling cannot quietly open a path for swarm
    follow to drive during a survey.
    """
    from rosy_core.navigation.manager import NavGoalSpec

    _client, svc = core_client()
    svc.nav.executor = RefusingExecutor()
    svc.nav.start_mapping(source="test")

    with pytest.raises(NavigationError) as raised:
        svc.nav.moving_goal(NavGoalSpec(x=1.0, y=0.0, yaw=0.0), source="swarm")

    assert raised.value.code == "MAPPING_ACTIVE"


def test_reset_without_an_open_session_is_400_not_a_quiet_200(core_client, events):
    """The second of the two lies.

    Resetting outside a mapping session used to return early and still answer
    200. `save_map` already had the honest answer for the same condition, so
    this reuses its error rather than inventing a second vocabulary for one
    situation.
    """
    client, svc = core_client()
    svc.nav.executor = RefusingExecutor()
    seen = events(svc)

    assert svc.nav.mapping_active is False
    response = client.post("/api/v1/slam/reset", headers=OPERATOR)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert seen == []
