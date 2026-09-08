"""FormationSession — 무장은 전부 아니면 전무, HOLD 는 릴레이를 멈추는 것(D-35 후보),
재개는 운영자만 한다."""

import asyncio

import pytest
from fakes import END, FakeRelay, FakeRobot, run, settle

from rosy_core.protocol.schemas import RobotMode, SwarmFollowParams
from rosy_fleet.formation.geometry import Formation, SlotOffset
from rosy_fleet.swarm.session import (
    ArmingFailed,
    FormationSession,
    FormationSpec,
    HoldPolicy,
    MapMismatch,
    SessionError,
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


def test_swarm_hold_is_not_a_trigger_and_holding_keeps_further_triggers_for_the_operator():
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
        assert leader.calls.count(("navigation_cancel",)) == cancels   # 두 번 세우지 않는다
        assert s.pending_triggers == [("nav.stuck", "rosy_03")]        # 버리지도 않는다
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
        await s.stop()
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
        await s.stop()
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


# --- 무장 중에 걸린 트리거, 끝난 세션의 감시, 되돌려지지 않은 무장 -------------------


def test_a_hold_trigger_that_lands_while_rearming_is_not_erased_by_the_reform():
    """무장은 await 여러 개짜리 구간이다. 그 사이에 걸린 HOLD 를 재개가 지우면 안 된다."""
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.start()
        gate = asyncio.Event()
        followers[0].follow_gate = gate                  # 재무장이 여기서 멈춘다
        task = asyncio.create_task(s.reform(FormationSpec(Formation.LINE, spacing=0.6)))
        await settle()
        followers[1].event_frames.put_nowait({"type": "safety.estop", "robot_id": "rosy_03",
                                              "data": {}})
        await settle()
        assert s.state is SessionState.HOLDING           # 무장 중에 걸렸다
        gate.set()
        await task                                       # reform 은 정상 반환한다
        assert s.state is SessionState.HOLDING           # 그러나 재개하지는 않는다
        assert s.relay.paused
        assert s.reason == ("safety.estop", "rosy_03")
        assert all(len(_follows(f)) == 2 for f in followers)   # 새 오프셋 무장은 살린다
        assert all(_follows(f)[1].distance == 0.0 for f in followers)
        assert leader.calls.count(("navigation_cancel",)) == 1
        await s.stop()
    run(main())


def test_an_abort_that_lands_while_rearming_disarms_the_robots_the_reform_just_armed():
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log, policy=HoldPolicy.ABORT)
        await s.start()
        gate = asyncio.Event()
        followers[0].follow_gate = gate
        before = {f.robot_id: f.calls.count(("swarm_cancel",)) for f in followers}
        watchers = list(s._watchers)          # abort 는 목록을 비운다 — 그 전에 잡아 둔다
        task = asyncio.create_task(s.reform(FormationSpec(Formation.LINE, spacing=0.6)))
        await settle()
        followers[1].event_frames.put_nowait({"type": "nav.stuck", "robot_id": "rosy_03",
                                              "data": {}})
        await settle()
        assert s.state is SessionState.STOPPED
        gate.set()
        with pytest.raises(SessionError):
            await task                                   # 재개하지 않고 끝난다
        assert s.state is SessionState.STOPPED
        assert s.relay.stopped
        # 죽은 릴레이를 보고 있는 팔로워를 남기지 않는다 — 재무장분까지 다시 푼다.
        for f in followers:
            assert f.calls.count(("swarm_cancel",)) - before[f.robot_id] >= 2
        last_follow = max(i for i, c in enumerate(followers[0].calls) if c[0] == "follow")
        assert ("swarm_cancel",) in followers[0].calls[last_follow:]
        await settle()
        assert watchers and all(t.done() for t in watchers)
    run(main())


def test_an_aborted_session_lets_go_of_its_event_sockets():
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log, policy=HoldPolicy.ABORT)
        await s.start()
        watchers = list(s._watchers)          # abort 는 목록을 비운다 — 그 전에 잡아 둔다
        followers[0].event_frames.put_nowait({"type": "nav.stuck", "robot_id": "rosy_02",
                                              "data": {}})
        await settle()
        assert s.state is SessionState.STOPPED
        assert watchers and all(t.done() for t in watchers)
        opens = {f.robot_id: f.event_opens for f in followers}
        followers[1].event_frames.put_nowait(END)        # 끝난 세션은 소켓을 다시 열지 않는다
        await settle(40)
        assert {f.robot_id: f.event_opens for f in followers} == opens
        await s.stop()
    run(main())


def test_an_arming_failure_with_an_unknown_outcome_also_disarms_the_robot_that_did_not_answer():
    async def main():
        leader, followers, log = _robots(2)
        followers[1].follow_error = ConnectionError("socket died mid-call")
        s = _session(leader, followers, log=log)
        with pytest.raises(ArmingFailed) as exc:
            await s.start()
        assert exc.value.robot_id == "rosy_03" and exc.value.code == "TRANSPORT"
        # 타임아웃 뒤에 로봇이 follow 를 받아 놓았을 수 있다. 거절과 달리 결과를 모른다.
        assert ("swarm_cancel",) in followers[1].calls
        assert ("swarm_cancel",) in followers[0].calls
        assert s.state is SessionState.STOPPED
    run(main())


def test_a_follower_that_left_the_formation_while_holding_blocks_resume_until_a_reform():
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.start()
        followers[0].event_frames.put_nowait({"type": "nav.blocked", "robot_id": "rosy_02",
                                              "data": {}})
        await settle()
        assert s.state is SessionState.HOLDING
        followers[1]._swarm_state = {"active": False, "holding": False}
        followers[1].event_frames.put_nowait(END)        # 이벤트 소켓 단절 → reconcile
        await settle(40)
        assert s.pending_triggers == [("swarm.aborted", "rosy_03")]
        with pytest.raises(SessionError):
            await s.resume()                             # 반쪽 대형으로 스트림을 켜지 않는다
        assert s.state is SessionState.HOLDING
        followers[1]._swarm_state = {"active": True, "holding": False}
        await s.reform(FormationSpec(Formation.LINE, spacing=0.6))
        assert s.state is SessionState.RUNNING           # 재무장이 그것을 처리했다
        assert s.pending_triggers == []
        assert not s.relay.paused
        await s.stop()
    run(main())


def test_a_second_trigger_while_holding_is_kept_and_only_a_reform_clears_it():
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.start()
        followers[0].event_frames.put_nowait({"type": "nav.blocked", "robot_id": "rosy_02",
                                              "data": {}})
        await settle()
        assert s.state is SessionState.HOLDING
        cancels = leader.calls.count(("navigation_cancel",))
        followers[1].event_frames.put_nowait({"type": "safety.estop", "robot_id": "rosy_03",
                                              "data": {}})
        await settle()
        assert s.pending_triggers == [("safety.estop", "rosy_03")]
        assert leader.calls.count(("navigation_cancel",)) == cancels
        assert s.reason == ("nav.blocked", "rosy_02")    # 첫 사유는 그대로다
        with pytest.raises(SessionError):
            await s.resume()
        await s.reform(FormationSpec(Formation.LINE, spacing=0.6))
        assert s.state is SessionState.RUNNING and s.pending_triggers == []
        await s.stop()
    run(main())


def test_a_relay_that_cannot_be_built_does_not_leave_the_followers_armed():
    async def main():
        leader, followers, _ = _robots(2)

        def broken(_leader, _followers, **_kw):
            raise ValueError("relay refused the robot set")

        s = FormationSession(leader, followers, FormationSpec(Formation.COLUMN, spacing=0.6),
                             relay_factory=broken, sleep=_no_sleep)
        with pytest.raises(SessionError):
            await s.start()
        assert s.state is SessionState.STOPPED
        assert all(("swarm_cancel",) in f.calls for f in followers)
        assert s.reason[0].startswith("relay_failed")
    run(main())


def test_the_session_refuses_duplicate_or_self_following_robots():
    spec = FormationSpec(Formation.COLUMN, spacing=0.6)
    with pytest.raises(ValueError):
        FormationSession(FakeRobot("rosy_01"), [FakeRobot("rosy_02"), FakeRobot("rosy_02")], spec)
    with pytest.raises(ValueError):
        FormationSession(FakeRobot("rosy_01"), [FakeRobot("rosy_02"), FakeRobot("rosy_01")], spec)


def test_a_leader_found_in_estop_after_a_socket_drop_holds_the_formation():
    async def main():
        leader, followers, log = _robots(1)
        s = _session(leader, followers, log=log)
        await s.start()
        leader._state["mode"] = RobotMode.EMERGENCY.value   # 끊긴 동안 e-stop 이 눌렸다
        leader.event_frames.put_nowait(END)
        await settle(40)
        assert leader.event_opens >= 2
        assert s.state is SessionState.HOLDING
        assert s.reason == ("safety.estop", "rosy_01")
        assert s.relay.paused
        await s.stop()
    run(main())


# --- 재개 직전에 들어온 것, 되지 않는 릴레이 정지, e-stop 상태의 리더 ------------------


def test_a_trigger_that_lands_while_resume_is_checking_blocks_the_resume():
    """재개 전 확인도 await 여러 개짜리 구간이다. 그 사이에 온 사고를 재개가 지나칠 수 없다."""
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.start()
        followers[0].event_frames.put_nowait({"type": "nav.blocked", "robot_id": "rosy_02",
                                              "data": {}})
        await settle()
        assert s.state is SessionState.HOLDING
        gate = asyncio.Event()
        followers[1].swarm_state_gate = gate              # 확인이 여기서 멈춘다
        task = asyncio.create_task(s.resume())
        await settle()
        followers[0].event_frames.put_nowait({"type": "safety.estop", "robot_id": "rosy_02",
                                              "data": {}})
        await settle()
        gate.set()
        with pytest.raises(SessionError):
            await task
        assert s.relay.paused                             # 풀지 않았다
        assert s.state is SessionState.HOLDING
        assert s.pending_triggers == [("safety.estop", "rosy_02")]
        await s.stop()
    run(main())


def test_a_stop_that_lands_while_resume_is_checking_is_not_overridden():
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.start()
        followers[0].event_frames.put_nowait({"type": "nav.blocked", "robot_id": "rosy_02",
                                              "data": {}})
        await settle()
        assert s.state is SessionState.HOLDING
        gate = asyncio.Event()
        followers[1].swarm_state_gate = gate
        task = asyncio.create_task(s.resume())
        await settle()
        await s.stop()                                    # 확인 중에 운영자가 끝냈다
        assert s.state is SessionState.STOPPED
        gate.set()
        try:
            await task
        except SessionError:
            pass
        assert s.state is SessionState.STOPPED            # 재개가 되살리지 않는다
        assert s.relay.stopped
    run(main())


def test_the_same_trigger_from_the_same_robot_is_only_kept_once():
    """끊긴 이벤트 소켓은 2 s 마다 다시 열린다. 같은 사고를 무한히 쌓으면 안 된다."""
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.start()
        followers[0].event_frames.put_nowait({"type": "nav.blocked", "robot_id": "rosy_02",
                                              "data": {}})
        await settle()
        assert s.state is SessionState.HOLDING
        followers[0]._swarm_state = {"active": False, "holding": False}
        for _ in range(3):
            followers[0].event_frames.put_nowait(END)     # 소켓 단절 → reconcile
            await settle(40)
        assert followers[0].event_opens >= 4
        assert s.pending_triggers.count(("swarm.aborted", "rosy_02")) == 1
        assert s.pending_triggers == [("swarm.aborted", "rosy_02")]
        await s.stop()
    run(main())


def test_an_abort_lets_the_robots_go_even_when_the_relay_cannot_be_stopped():
    async def main():
        leader, followers, log = _robots(2)

        class BrokenStopRelay(FakeRelay):
            async def stop(self):
                self.log.append(("relay", "stop"))
                raise ConnectionError("relay socket already gone")

        s = FormationSession(leader, followers, FormationSpec(Formation.COLUMN, spacing=0.6),
                             policy=HoldPolicy.ABORT, sleep=_no_sleep,
                             relay_factory=lambda ld, f, **_: BrokenStopRelay(ld, f, log=log))
        await s.start()
        followers[0].event_frames.put_nowait({"type": "nav.stuck", "robot_id": "rosy_02",
                                              "data": {}})
        await settle()
        # 릴레이를 못 끄는 것은 로봇을 무장한 채 두는 이유가 되지 못한다.
        assert all(("swarm_cancel",) in f.calls for f in followers)
        assert ("navigation_cancel",) in leader.calls
        assert s.state is SessionState.STOPPED
        await s.stop()
    run(main())


def test_a_leader_in_estop_is_refused_before_any_follower_is_armed():
    async def main():
        leader, followers, log = _robots(2)
        leader._state["mode"] = RobotMode.EMERGENCY.value
        s = _session(leader, followers, log=log)
        with pytest.raises(ArmingFailed) as exc:
            await s.start()
        assert exc.value.robot_id == "rosy_01" and exc.value.code == "EMERGENCY_ACTIVE"
        assert not any(_follows(f) for f in followers)
        assert s.state is SessionState.STOPPED
    run(main())


def test_resume_refuses_while_the_leader_is_still_in_estop():
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.start()
        leader._state["mode"] = RobotMode.EMERGENCY.value
        leader.event_frames.put_nowait({"type": "safety.estop", "robot_id": "rosy_01", "data": {}})
        await settle()
        assert s.state is SessionState.HOLDING
        with pytest.raises(SessionError):
            await s.resume()                              # 리더가 아직 서 있다
        assert s.state is SessionState.HOLDING and s.relay.paused
        leader._state["mode"] = RobotMode.IDLE.value      # e-stop 이 풀렸다
        await s.resume()
        assert s.state is SessionState.RUNNING and not s.relay.paused
        await s.stop()
    run(main())


def test_a_relay_that_cannot_be_started_does_not_leave_the_followers_armed():
    async def main():
        leader, followers, log = _robots(2)
        created = []

        class BrokenStartRelay(FakeRelay):
            async def start(self):
                raise ConnectionError("reference socket refused")

        def factory(ld, f, **_):
            relay = BrokenStartRelay(ld, f, log=log)
            created.append(relay)
            return relay

        s = FormationSession(leader, followers, FormationSpec(Formation.COLUMN, spacing=0.6),
                             relay_factory=factory, sleep=_no_sleep)
        with pytest.raises(SessionError):
            await s.start()
        assert s.state is SessionState.STOPPED
        assert all(("swarm_cancel",) in f.calls for f in followers)
        assert created[0].stopped
        assert s.reason[0].startswith("relay_failed")
    run(main())


def test_a_reform_from_a_hold_carries_only_what_was_already_there():
    """HOLDING 중의 reform 은 시작 시점에 쌓여 있던 몫만 책임진다."""
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.start()
        followers[0].event_frames.put_nowait({"type": "nav.blocked", "robot_id": "rosy_02",
                                              "data": {}})
        await settle()
        followers[1].event_frames.put_nowait({"type": "safety.estop", "robot_id": "rosy_03",
                                              "data": {}})
        await settle()
        assert s.pending_triggers == [("safety.estop", "rosy_03")]
        gate = asyncio.Event()
        followers[0].follow_gate = gate
        task = asyncio.create_task(s.reform(FormationSpec(Formation.LINE, spacing=0.6)))
        await settle()
        followers[1].event_frames.put_nowait({"type": "nav.stuck", "robot_id": "rosy_03",
                                              "data": {}})
        await settle()
        gate.set()
        await task
        assert s.state is SessionState.HOLDING
        assert s.pending_triggers == [("nav.stuck", "rosy_03")]   # 새로 온 것만 남는다
        assert s.relay.paused
        await s.stop()
    run(main())


def test_stop_from_idle_has_nothing_to_cancel():
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.stop()
        assert s.state is SessionState.STOPPED
        assert not any(("swarm_cancel",) in f.calls for f in followers)
        assert not any(entry[1] == "swarm_cancel" for entry in log)
    run(main())
