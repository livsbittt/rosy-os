#!/usr/bin/env python3
"""Swarm formation bench — 리더를 몰고 팔로워를 계측한다. rclpy 없이 rosy_fleet 만 쓴다.

시나리오:
  follow  3대 COLUMN, 리더가 waypoint 를 순회. slot_err_m 과 stream 주기.
  reform  주행 중 LINE → V. 재배정과 수렴.
  hold    릴레이 pause 주입 → 전원 holding 까지의 시간.
  stuck   팔로워 하나 앞에 장애물 스폰 → nav.stuck → 세션 HOLDING 까지의 시간.

CSV 열: t, scenario, robot_id, state, holding, stream_age_s, slot_err_m, relay_tx_hz,
        leader_rx_hz, leader_age_s

Design: docs/plans/2026-09-08-swarm-formation-slice-design.md §8.2
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import math
import subprocess
import sys
import time
from pathlib import Path

from rosy_fleet.formation.geometry import Formation, slot_world_position
from rosy_fleet.swarm.robots import load_robots
from rosy_fleet.swarm.session import FormationSession, FormationSpec, SessionState
from rosy_fleet.swarm.transport import HttpRobotClient

OBSTACLE_SDF = """<sdf version='1.9'><model name='{name}'><static>true</static>
<link name='l'><collision name='c'><geometry><box><size>0.3 0.6 0.5</size></box></geometry></collision>
<visual name='v'><geometry><box><size>0.3 0.6 0.5</size></box></geometry></visual></link></model></sdf>"""


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="swarm_bench")
    p.add_argument("--robots", type=Path, required=True, help="gz_multi core:=true 가 쓴 robots.yaml")
    p.add_argument("--leader", default="rosy_01")
    p.add_argument("--scenario", choices=["follow", "reform", "hold", "stuck"], default="follow")
    p.add_argument("--formation", default="COLUMN", choices=[f.value for f in Formation])
    p.add_argument("--spacing", type=float, default=0.6)
    p.add_argument("--waypoints", default="1.5,0,0;1.5,1.0,1.57;0,1.0,3.14;0,0,0",
                   help="x,y,yaw;x,y,yaw;... (리더 목표 순서)")
    p.add_argument("--duration", type=float, default=90.0, help="계측 시간 (s)")
    p.add_argument("--inject-at", type=float, default=30.0, help="hold/stuck 주입 시각 (s)")
    p.add_argument("--world", default="rosy_factory")
    p.add_argument("--out", type=Path, default=Path("swarm_bench.csv"))
    return p.parse_args(argv)


def _parse_waypoints(text: str) -> list[tuple[float, float, float]]:
    out = []
    for chunk in text.split(";"):
        x, y, yaw = (float(v) for v in chunk.split(","))
        out.append((x, y, yaw))
    return out


async def _drive_leader(leader: HttpRobotClient, waypoints, stop: asyncio.Event) -> None:
    """리더에 목표를 차례로 건다. 다음 목표는 항법이 IDLE/ARRIVED 로 돌아오면."""
    i = 0
    while not stop.is_set():
        x, y, yaw = waypoints[i % len(waypoints)]
        try:
            await leader.navigation_goal(x, y, yaw)
        except Exception as exc:
            print(f"leader goal refused: {exc}", file=sys.stderr)
            await asyncio.sleep(2.0)
            continue
        await asyncio.sleep(2.0)
        while not stop.is_set():
            state = await leader.state()
            if state.get("navigation") in ("IDLE", "ARRIVED", "FAILED", "CANCELED", "BLOCKED"):
                break
            await asyncio.sleep(0.5)
        i += 1


def _spawn_obstacle(world: str, x: float, y: float, name: str) -> None:
    # SDF 템플릿은 홑따옴표만 쓰므로 protobuf 텍스트의 쌍따옴표 안에 그대로 들어간다.
    sdf = OBSTACLE_SDF.format(name=name).replace("\n", " ")
    req = f'sdf: "{sdf}" pose: {{position: {{x: {x}, y: {y}, z: 0.25}}}}'
    subprocess.run(["gz", "service", "-s", f"/world/{world}/create",
                    "--reqtype", "gz.msgs.EntityFactory", "--reptype", "gz.msgs.Boolean",
                    "--timeout", "2000", "--req", req], check=False)


async def main_async(args) -> int:
    robots = load_robots(args.robots)
    clients = {r.robot_id: HttpRobotClient(r) for r in robots}
    leader = clients[args.leader]
    followers = [c for rid, c in clients.items() if rid != args.leader]
    spec = FormationSpec(Formation(args.formation), spacing=args.spacing)
    session = FormationSession(leader, followers, spec)
    await session.start()
    print(f"armed: {session.assignment}")

    stop = asyncio.Event()
    driver = asyncio.create_task(_drive_leader(leader, _parse_waypoints(args.waypoints), stop))
    t0 = time.monotonic()
    injected = False
    inject_t = None
    reached_t = None

    with args.out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["t", "scenario", "robot_id", "state", "holding", "stream_age_s", "slot_err_m", "relay_tx_hz",
                    "leader_rx_hz", "leader_age_s"])
        try:
            while time.monotonic() - t0 < args.duration:
                t = time.monotonic() - t0
                if not injected and t >= args.inject_at and args.scenario in ("reform", "hold", "stuck"):
                    injected, inject_t = True, t
                    if args.scenario == "reform":
                        await session.reform(FormationSpec(Formation.V, spacing=args.spacing))
                    elif args.scenario == "hold":
                        session.relay.pause()
                    else:
                        victim = followers[0]
                        st = await victim.state()
                        pose = st.get("pose") or {}
                        yaw = float(pose.get("yaw", 0.0))
                        _spawn_obstacle(args.world, float(pose["x"]) + 0.5 * math.cos(yaw),
                                        float(pose["y"]) + 0.5 * math.sin(yaw), "bench_block")
                lstate = await leader.state()
                lp = lstate.get("pose") or {}
                stats = session.relay.stats()
                all_holding = True
                for f in followers:
                    sw = await f.swarm_state()
                    st = await f.state()
                    fp = st.get("pose") or {}
                    off = session.assignment.get(f.robot_id)
                    err = ""
                    if off is not None:
                        sx, sy = slot_world_position(
                            off, float(lp.get("x", 0)), float(lp.get("y", 0)), float(lp.get("yaw", 0)))
                        err = f"{math.dist((sx, sy), (float(fp.get('x', 0)), float(fp.get('y', 0)))):.3f}"
                    holding = bool(sw.get("holding"))
                    all_holding = all_holding and holding
                    w.writerow([f"{t:.1f}", args.scenario, f.robot_id, session.state.value, holding,
                                sw.get("stream_age_s"), err, f"{stats.follower_tx_hz.get(f.robot_id, 0.0):.1f}",
                                f"{stats.leader_rx_hz:.1f}",
                                "" if stats.leader_age_s is None else f"{stats.leader_age_s:.2f}"])
                fh.flush()
                if injected and reached_t is None:
                    if args.scenario == "hold" and all_holding:
                        reached_t = t
                        print(f"HOLD reached after {reached_t - inject_t:.2f} s")
                    if args.scenario == "stuck" and session.state is SessionState.HOLDING:
                        reached_t = t
                        print(f"FOR-004 HOLD after {reached_t - inject_t:.2f} s: {session.reason}")
                await asyncio.sleep(1.0)
        finally:
            stop.set()
            driver.cancel()
            await session.stop()
            for c in clients.values():
                await c.aclose()
    print(f"wrote {args.out}")
    return 0


def main(argv=None) -> int:
    return asyncio.run(main_async(parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
