"""FormationSession — 무장은 전부 아니면 전무, HOLD 는 릴레이를 멈추는 것(D-35 후보),
재개는 운영자만 한다."""

import asyncio

import pytest
from fakes import END, FakeRelay, FakeRobot, run, settle

from rosy_core.protocol.schemas import SwarmFollowParams
from rosy_fleet.formation.geometry import Formation, SlotOffset
from rosy_fleet.swarm.session import (
    ArmingFailed,
    FormationSession,
    FormationSpec,
    HoldPolicy,
    MapMismatch,
    SessionState,
)
from rosy_fleet.swarm.transport import RobotApiError


def _robots(n=2, log=None, leader_pose=(0.0, 0.0, 0.0)):
    log = log if log is not None else []
    leader = FakeRobot("rosy_01", log=log, state={
        "robot_id": "rosy_01", "map_id": "m1",
        "pose": {"x": leader_pose[0], "y": leader_pose[1], "yaw": leader_pose[2]}})
    followers = [FakeRobot(f"rosy_{i:02d}", log=log) for i in range(2, 2 + n)]
    return leader, followers, log


async def _no_sleep(_s):
    await asyncio.sleep(0)


def _session(leader, followers, spec=None, log=None, **kw):
    spec = spec or FormationSpec(Formation.COLUMN, spacing=0.6)
    kw.setdefault("sleep", _no_sleep)
    return FormationSession(leader, followers, spec,
                            relay_factory=lambda ld, f, **_: FakeRelay(ld, f, log=log), **kw)


def _follows(robot):
    return [c[1] for c in robot.calls if c[0] == "follow"]


def test_start_arms_every_follower_with_its_slot_and_then_starts_the_relay():
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.start()
        assert s.state is SessionState.RUNNING
        params = {f.robot_id: _follows(f)[0] for f in followers}
        assert all(isinstance(p, SwarmFollowParams) for p in params.values())
        assert {p.target_robot_id for p in params.values()} == {"rosy_01"}
        assert sorted(p.distance for p in params.values()) == [0.6, 1.2]
        assert all(p.max_speed == 0.15 and p.stream_timeout_ms == 1000 for p in params.values())
        kinds = [entry[1] for entry in log if entry[0] == "relay" or entry[1] == "follow"]
        assert kinds.index("start") > max(i for i, k in enumerate(kinds) if k == "follow")
        await s.stop()
    run(main())


def test_the_nearest_follower_takes_the_nearest_slot():
    async def main():
        leader, followers, log = _robots(2)
        # V, spacing 0.6: 슬롯은 리더 뒤 0.6, 좌 +0.6 / 우 −0.6. rosy_02 는 왼쪽에 있다.
        followers[0]._state["pose"] = {"x": -0.6, "y": 0.6, "yaw": 0.0}
        followers[1]._state["pose"] = {"x": -0.6, "y": -0.6, "yaw": 0.0}
        s = _session(leader, followers, spec=FormationSpec(Formation.V, spacing=0.6), log=log)
        await s.start()
        assert s.assignment["rosy_02"] == SlotOffset(0.6, 0.6)
        assert s.assignment["rosy_03"] == SlotOffset(0.6, -0.6)
        await s.stop()
    run(main())


def test_one_refused_follow_cancels_the_ones_already_armed_and_never_starts_the_relay():
    async def main():
        leader, followers, log = _robots(2)
        followers[1].follow_error = RobotApiError("rosy_03", 409, "DOCKING_ACTIVE", "busy")
        s = _session(leader, followers, log=log)
        with pytest.raises(ArmingFailed) as exc:
            await s.start()
        assert exc.value.robot_id == "rosy_03" and exc.value.code == "DOCKING_ACTIVE"
        assert ("swarm_cancel",) in followers[0].calls
        assert ("relay", "start") not in log
        assert s.state is SessionState.STOPPED
    run(main())


def test_a_map_mismatch_is_refused_before_any_follow():
    async def main():
        leader, followers, log = _robots(2)
        followers[1]._state["map_id"] = "other"
        s = _session(leader, followers, log=log)
        with pytest.raises(MapMismatch):
            await s.start()
        assert not any(_follows(f) for f in followers)
    run(main())


def test_a_robot_without_a_map_id_does_not_block_the_start():
    async def main():
        leader, followers, log = _robots(2)
        followers[1]._state["map_id"] = None
        s = _session(leader, followers, log=log)
        await s.start()
        assert s.state is SessionState.RUNNING
        await s.stop()
    run(main())


@pytest.mark.parametrize("event_type", ["nav.stuck", "nav.failed", "nav.blocked",
                                        "swarm.aborted", "safety.estop"])
def test_each_for_004_trigger_pauses_the_relay_and_cancels_the_leader(event_type):
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.start()
        followers[0].event_frames.put_nowait({"type": event_type, "robot_id": "rosy_02", "data": {}})
        await settle()
        assert s.state is SessionState.HOLDING
        assert s.reason == (event_type, "rosy_02")
        assert s.relay.paused
        assert ("navigation_cancel",) in leader.calls
        assert log.index(("relay", "pause")) < log.index(("rosy_01", "navigation_cancel"))
        await s.stop()
    run(main())


def test_a_trigger_on_the_leader_counts_too():
    async def main():
        leader, followers, log = _robots(1)
        s = _session(leader, followers, log=log)
        await s.start()
        leader.event_frames.put_nowait({"type": "nav.failed", "robot_id": "rosy_01", "data": {}})
        await settle()
        assert s.state is SessionState.HOLDING
        await s.stop()
    run(main())


def test_swarm_hold_is_not_a_trigger_and_holding_ignores_further_events():
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.start()
        followers[0].event_frames.put_nowait({"type": "swarm.hold", "robot_id": "rosy_02",
                                              "data": {"reason": "map_mismatch"}})
        await settle()
        assert s.state is SessionState.RUNNING
        followers[0].event_frames.put_nowait({"type": "nav.stuck", "robot_id": "rosy_02", "data": {}})
        await settle()
        assert s.state is SessionState.HOLDING
        cancels = leader.calls.count(("navigation_cancel",))
        followers[1].event_frames.put_nowait({"type": "swarm.hold", "robot_id": "rosy_03",
                                              "data": {"reason": "reference stream lost"}})
        followers[1].event_frames.put_nowait({"type": "nav.stuck", "robot_id": "rosy_03", "data": {}})
        await settle()
        assert leader.calls.count(("navigation_cancel",)) == cancels   # 두 번 처리하지 않는다
        await s.stop()
    run(main())


def test_resume_is_the_only_way_back_to_running():
    async def main():
        leader, followers, log = _robots(1)
        s = _session(leader, followers, log=log)
        await s.start()
        followers[0].event_frames.put_nowait({"type": "nav.blocked", "robot_id": "rosy_02", "data": {}})
        await settle()
        assert s.state is SessionState.HOLDING
        await settle(50)
        assert s.state is SessionState.HOLDING            # 시간이 지나도 스스로 돌아오지 않는다
        await s.resume()
        assert s.state is SessionState.RUNNING and not s.relay.paused and s.reason is None
        await s.resume()                                   # RUNNING 에서 resume 은 무해하다
        assert s.state is SessionState.RUNNING
        await s.stop()
    run(main())


def test_the_abort_policy_cancels_every_follower_and_ends_the_session():
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log, policy=HoldPolicy.ABORT)
        await s.start()
        followers[0].event_frames.put_nowait({"type": "nav.stuck", "robot_id": "rosy_02", "data": {}})
        await settle()
        assert s.state is SessionState.STOPPED
        assert all(("swarm_cancel",) in f.calls for f in followers)
        assert ("navigation_cancel",) in leader.calls
        assert s.relay.stopped
    run(main())


def test_reform_pauses_rearms_with_the_new_offsets_and_resumes():
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.start()
        mark = len(log)
        await s.reform(FormationSpec(Formation.LINE, spacing=0.6))
        tail = log[mark:]
        assert tail[0] == ("relay", "pause")
        assert tail[-1] == ("relay", "resume")
        second = {f.robot_id: _follows(f)[1] for f in followers}
        assert sorted(p.lateral for p in second.values()) == [-0.6, 0.6]
        assert all(p.distance == 0.0 for p in second.values())
        assert s.state is SessionState.RUNNING
        await s.stop()
    run(main())


def test_a_failed_reform_ends_the_session_because_half_a_formation_cannot_be_resumed():
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.start()
        followers[1].follow_error = RobotApiError("rosy_03", 409, "EMERGENCY_ACTIVE", "estop")
        with pytest.raises(ArmingFailed):
            await s.reform(FormationSpec(Formation.LINE, spacing=0.6))
        # 재무장된 팔로워는 이미 풀렸고 나머지는 옛 오프셋을 쥐고 있다. 그 상태로 스트림을
        # 다시 켜면 대형이 둘로 갈린다 — HOLD 가 아니라 종료가 정직하다.
        assert s.state is SessionState.STOPPED
        assert s.reason[0].startswith("reform_failed")
        assert all(("swarm_cancel",) in f.calls for f in followers)
        assert ("navigation_cancel",) in leader.calls
        assert s.relay.stopped
    run(main())


def test_stop_cancels_every_follower_and_stops_the_relay():
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.start()
        await s.stop()
        assert s.state is SessionState.STOPPED
        assert all(("swarm_cancel",) in f.calls for f in followers)
        assert ("navigation_cancel",) not in leader.calls     # 리더 항법은 운영자의 것
        assert s.relay.stopped
    run(main())


def test_an_events_socket_that_drops_is_reopened_and_a_follower_found_inactive_is_an_abort():
    async def main():
        leader, followers, log = _robots(1)
        s = _session(leader, followers, log=log)
        await s.start()
        followers[0]._swarm_state = {"active": False, "holding": False}
        followers[0].event_frames.put_nowait(END)          # 이벤트 소켓 단절
        await settle(40)
        assert followers[0].event_opens >= 2
        assert s.state is SessionState.HOLDING
        assert s.reason == ("swarm.aborted", "rosy_02")
        await s.stop()
    run(main())


def test_a_quietly_closed_events_socket_is_reopened_with_backoff_not_a_tight_loop():
    async def main():
        sleeps = []

        async def sleep(s):
            sleeps.append(s)
            await asyncio.sleep(0)

        leader, followers, log = _robots(1)
        s = FormationSession(leader, followers, FormationSpec(Formation.COLUMN, spacing=0.6),
                             relay_factory=lambda ld, f, **_: FakeRelay(ld, f, log=log), sleep=sleep)
        await s.start()
        for _ in range(4):
            followers[0].event_frames.put_nowait(END)     # 소켓이 조용히 닫힌다, 반복해서
            await settle(10)
        follower_sleeps = [x for x in sleeps if x > 0]
        assert len(follower_sleeps) >= 3                 # 매번 기다린다
        assert follower_sleeps[1] > follower_sleeps[0]   # 커진다
        assert max(follower_sleeps) <= 2.0
        await s.stop()
    run(main())
