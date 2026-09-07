# Dock Detector Measurement Rig Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the rig that decides the dock detector by measurement — a ROS-free geometric fit plus a record-and-verdict layer, fed by a Gazebo sweep and a robot bench probe.

**Architecture:** Two new ROS-free siblings under `rosy_core/docking/` own everything that decides: `profile.py` fits three asymmetric posts in a flat scan and returns a `base_link` pose, `probe.py` owns the CSV schema and the verdict. Two collection lanes write the same schema and pass the same verdict function — a Gazebo sweep (no hardware) and a `dock_probe` console script on the robot. Nothing is wired into `services.py` and no capability flag changes.

**Design:** [2026-09-07-dock-detector-measurement-rig-design.md](2026-09-07-dock-detector-measurement-rig-design.md)

**Depends on:** the docking state machine — landed. `DockObservation` in `rosy_core/docking/detector.py` is the contract `fit()` produces.

**Tech Stack:** Python 3.12, pydantic v2, pytest (host), ROS 2 `rclpy` + `sensor_msgs` (bench lane), Gazebo `gz-sim8` SDF (sim lane), bash

---

## Where the work lands

| File | Responsibility | Host-testable |
|---|---|---|
| `src/rosy_core/rosy_core/docking/profile.py` | Dock shape config, scan → `base_link` pose, rejection reasons | **yes** |
| `src/rosy_core/rosy_core/docking/probe.py` | CSV schema, append/read, the verdict that picks a candidate | **yes** |
| `src/rosy_core/test/test_dock_profile.py` | Fit correctness, noise budget, false-positive refusals | yes |
| `src/rosy_core/test/test_dock_probe.py` | Round trip, verdict pass and fail for all three candidates | yes |
| `src/rosy_gz_sim/models/dock/model.sdf` + `model.config` | Measurement dock: three posts at scan height, static | no |
| `src/rosy_gz_sim/scripts/dock_sweep.py` | Moves the dock, samples `/scan`, appends rows | no (needs Gazebo) |
| `src/rosy_bringup/rosy_bringup/dock_probe.py` | One bench capture: `/scan` + `/ir_sensor/range` → one row | arg parsing only |
| `deploy/robot/measure-dock-baseline.sh` | Bench procedure wrapper, in the shape of `measure-dds-baseline.sh` | no |
| `docs/deployment/pi5-acceptance-checklist.md` | §7.6 gains the measurement items | no |

Tasks 1–7 run on the Windows dev host with plain pytest and are fully verifiable
now. Tasks 8–9 need Linux/WSL with Gazebo. Tasks 10–11 need the Pi.

**The ROS-free half of this plan was executed and run before the plan was
written.** `profile.py` and `test_dock_profile.py` were built in a scratch
directory and the 15 tests pass. That run changed the plan twice, and both
changes are folded in below:

- The first post-centre estimator took `min(range)` per cluster, which picks
  the worst noise sample. At the σ = 20 mm the simulator declares, it rejected
  45 of 200 correct docks and pushed the worst correct residual to 29.4 mm —
  past the 21.8 mm a wrong layout produces with no noise at all. No threshold
  could separate them. Averaging the arc and adding the (π/4)·r bias fixes it.
- `max_residual_m` moved from 10 mm to 18 mm, which is where the measured
  populations leave room: 13.0 mm worst correct, 21.8 mm wrong layout.

The numbers quoted in the tasks below are measured, not estimated.

---

### Task 1: Dock shape config, and the asymmetry it must have

**Files:**
- Create: `src/rosy_core/rosy_core/docking/profile.py`
- Create: `src/rosy_core/test/test_dock_profile.py`

- [ ] **Step 1: Write the failing test**

```python
"""Dock shape fitting from a flat scan (design: 2026-09-07 rig)."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from rosy_core.docking.profile import DockProfile, ProfileFit, SensorOffset


def test_the_default_profile_is_the_three_posts_the_design_settled_on():
    profile = DockProfile()
    assert profile.post_lateral_m == (-0.075, -0.015, 0.075)
    assert profile.post_radius_m == 0.015


def test_a_mirror_symmetric_layout_is_refused_at_config_time():
    # A symmetric layout admits a mirror solution, so yaw has no sign, and it
    # is also what two furniture legs plus a third look like. The design chose
    # asymmetry deliberately; the config refuses to lose it.
    with pytest.raises(ValidationError):
        DockProfile(post_lateral_m=(-0.075, 0.0, 0.075))


def test_fewer_than_three_posts_is_refused():
    with pytest.raises(ValidationError):
        DockProfile(post_lateral_m=(-0.075, 0.075))


def test_the_scanner_offset_defaults_to_where_the_c1_actually_sits():
    # rplidar_link is 17 mm behind base_link. A detector that forgets this
    # reports the dock 17 mm closer than it is, every time.
    sensor = SensorOffset()
    assert sensor.x == pytest.approx(-0.017)
    assert sensor.y == 0.0
    assert sensor.yaw == 0.0


def test_an_empty_fit_is_a_value_not_an_exception():
    empty = ProfileFit(reason="nothing tried")
    assert empty.found is False
    assert empty.observation is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/rosy_core && python -m pytest test/test_dock_profile.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'rosy_core.docking.profile'`

- [ ] **Step 3: Write the module with config and result types only**

Create `src/rosy_core/rosy_core/docking/profile.py`:

```python
"""rosy_core.docking.profile — 스캔에서 도크 기둥 배치를 찾아 상대 포즈를 낸다.

**횡방향은 방위각으로, 깊이만 거리로 잰다.** 방위각에는 거리 잡음이 없어서 이
추정기의 횡오차는 거리 잡음이 6배 변해도 거의 움직이지 않는다(5.25 → 4.94 mm).
그 성질이 V 면 대신 기둥을 고른 이유다 — V 는 26.2 → 2.1 mm 로 잡음에 비례해서,
통과 여부가 아직 아무도 재지 않은 C1 잡음에 인질로 잡힌다.

ROS 무의존 — 평평한 배열을 받고 `base_link` 기준 포즈를 돌려준다. 스캔 메시지를
보지 않으므로 host pytest 가 이 결정을 전부 본다(criterion C1).

설계: docs/plans/2026-09-07-dock-detector-measurement-rig-design.md
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

from pydantic import BaseModel, Field, field_validator

from rosy_core.docking.detector import DockObservation


def _wrap(angle: float) -> float:
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


class DockProfile(BaseModel):
    """도크의 LiDAR 가시 형상. 기종별 설정이다."""

    post_radius_m: float = Field(default=0.015, gt=0.0)
    #: 기둥의 횡 위치. 오름차순 대응은 방위각 순서로 성립한다.
    post_lateral_m: tuple[float, ...] = (-0.075, -0.015, 0.075)
    #: 18 mm 은 재서 고른 값이다. 시뮬 잡음 σ = 20 mm 에서 정상 도크의 최악
    #: residual 이 400회 중 13.0 mm 였고, 간격이 어긋난 배치는 잡음 없이도
    #: 21.8 mm 였다. 게이트는 그 둘 사이에 있어야 한다 — 좁히면 진짜 도크를
    #: 거부하고, 넓히면 아무 기둥 세 개나 도크가 된다.
    max_residual_m: float = Field(default=0.018, gt=0.0)
    min_points_per_post: int = Field(default=2, ge=2)
    search_half_angle_rad: float = Field(default=0.6, gt=0.0)
    max_range_m: float = Field(default=1.20, gt=0.0)

    @field_validator("post_lateral_m")
    @classmethod
    def _must_be_asymmetric(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        if len(value) < 3:
            # 두 개로는 거울 해가 남고, 가구 다리 한 쌍과 구별되지 않는다.
            raise ValueError("need at least three posts to break the mirror solution")
        ascending = sorted(value)
        mirrored = sorted(-item for item in value)
        if all(math.isclose(a, b, abs_tol=1e-9)
               for a, b in zip(ascending, mirrored)):
            raise ValueError("post_lateral_m must not be mirror-symmetric")
        return value


@dataclass(frozen=True)
class SensorOffset:
    """스캐너의 `base_link` 기준 설치 위치. C1 은 x=-0.017, y=0, yaw=0."""

    x: float = -0.017
    y: float = 0.0
    yaw: float = 0.0


@dataclass(frozen=True)
class ProfileFit:
    """피팅 1회 결과. 어떤 실패도 예외가 아니라 이 값으로 나온다 —
    `DockAgent.poll()` 이 세운 집 스타일 그대로다."""

    observation: Optional[DockObservation] = None
    reason: Optional[str] = None
    residual_m: Optional[float] = None
    points: int = 0
    clusters: int = 0

    @property
    def found(self) -> bool:
        return self.observation is not None
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd src/rosy_core && python -m pytest test/test_dock_profile.py -q`
Expected: PASS, 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/rosy_core/rosy_core/docking/profile.py src/rosy_core/test/test_dock_profile.py
git commit -m 'feat(dock): make the shape config refuse a layout with no yaw sign'
```

---

### Task 2: Clustering, and why the gap has to be angular

**Files:**
- Modify: `src/rosy_core/rosy_core/docking/profile.py`
- Modify: `src/rosy_core/test/test_dock_profile.py`

- [ ] **Step 1: Write the failing test**

Append to `src/rosy_core/test/test_dock_profile.py`:

```python
import random

from rosy_core.docking.profile import fit

STEP_SIM = math.radians(360.0 / 640.0)      # Gazebo declares 640 samples
STEP_C1 = math.radians(0.24)                # C1 DenseBoost, denser


def _scan_of_posts(profile, x, y, yaw, step=STEP_SIM, sigma=0.0, seed=1,
                   half=0.6, hide=()):
    """Raycast the posts of `profile` with the dock at a known sensor-frame pose.

    Returns (ranges, angle_min, angle_increment) the way a LaserScan carries it.
    `hide` drops posts by index, which is how occlusion is simulated.
    """
    rng = random.Random(seed)
    centres = []
    for index, lateral in enumerate(sorted(profile.post_lateral_m)):
        if index in hide:
            continue
        centres.append((x - lateral * math.sin(yaw), y + lateral * math.cos(yaw)))

    count = int(half / step)
    angle_min = -count * step
    ranges = []
    for index in range(2 * count + 1):
        bearing = angle_min + index * step
        dx, dy = math.cos(bearing), math.sin(bearing)
        best = math.inf
        for cx, cy in centres:
            along = dx * cx + dy * cy
            offset = cx * cx + cy * cy - profile.post_radius_m ** 2
            disc = along * along - offset
            if disc < 0.0 or along <= 0.0:
                continue
            hit = along - math.sqrt(disc)
            if 0.0 < hit < best:
                best = hit
        if math.isinf(best):
            ranges.append(math.inf)
        else:
            ranges.append(best + (rng.gauss(0.0, sigma) if sigma else 0.0))
    return ranges, angle_min, step


def _scan_of_wall(distance=0.5, step=STEP_SIM, half=0.6):
    count = int(half / step)
    angle_min = -count * step
    ranges = [distance / math.cos(angle_min + i * step)
              for i in range(2 * count + 1)]
    return ranges, angle_min, step


def test_an_empty_scan_is_refused_with_a_reason():
    profile = DockProfile()
    got = fit([math.inf] * 200, -0.6, STEP_SIM, profile, SensorOffset(), now=1.0)
    assert got.found is False
    assert got.reason


def test_a_plain_wall_is_never_a_dock():
    # The strongest criterion in the design: a confident wrong pose drives the
    # robot somewhere that is not the dock. A wall is one continuous cluster.
    profile = DockProfile()
    ranges, angle_min, step = _scan_of_wall()
    got = fit(ranges, angle_min, step, profile, SensorOffset(), now=1.0)
    assert got.found is False
    assert got.clusters == 1


def test_two_visible_posts_are_not_a_dock():
    profile = DockProfile()
    ranges, angle_min, step = _scan_of_posts(profile, 0.5, 0.0, 0.0, hide=(1,))
    got = fit(ranges, angle_min, step, profile, SensorOffset(), now=1.0)
    assert got.found is False
    assert got.clusters == 2


def test_three_posts_cluster_as_three_even_at_pessimistic_noise():
    # Clustering on range discontinuity loses 398 of 400 fits at sigma = 20 mm.
    # Angular gaps are noise-free, and this pins that choice.
    profile = DockProfile()
    ranges, angle_min, step = _scan_of_posts(
        profile, 0.5, 0.0, 0.0, sigma=0.020, seed=3)
    got = fit(ranges, angle_min, step, profile, SensorOffset(), now=1.0)
    assert got.clusters == 3
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/rosy_core && python -m pytest test/test_dock_profile.py -q`
Expected: FAIL — `ImportError: cannot import name 'fit'`

- [ ] **Step 3: Add the point extraction, clustering, and the rejection paths**

Append to `src/rosy_core/rosy_core/docking/profile.py`:

```python
def _forward_points(ranges: Sequence[float], angle_min: float,
                    angle_increment: float,
                    profile: DockProfile) -> list[tuple[float, float]]:
    """(방위각, 거리) 목록. 전방 창 밖·비유한·과대 거리는 버린다."""
    points: list[tuple[float, float]] = []
    for index, value in enumerate(ranges):
        bearing = _wrap(angle_min + index * angle_increment)
        if abs(bearing) > profile.search_half_angle_rad:
            continue
        try:
            distance = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(distance):
            continue
        if distance <= 0.0 or distance > profile.max_range_m:
            continue
        points.append((bearing, distance))
    points.sort()
    return points


def _cluster_by_angular_gap(points: list[tuple[float, float]],
                            angle_increment: float
                            ) -> list[list[tuple[float, float]]]:
    """각도 간극으로만 자른다.

    기둥 사이는 광선이 아무것도 맞히지 않아 방위각이 그냥 건너뛴다. 그 간극에는
    거리 잡음이 없다. 거리 불연속으로 자르면 σ = 20 mm 에서 클러스터가 갈라져
    400회 중 398회를 놓친다 — 실제로 그렇게 짜서 확인했다.
    """
    gap = 1.5 * abs(angle_increment)
    clusters: list[list[tuple[float, float]]] = []
    current = [points[0]]
    for previous, point in zip(points, points[1:]):
        if point[0] - previous[0] > gap:
            clusters.append(current)
            current = [point]
        else:
            current.append(point)
    clusters.append(current)
    return clusters


def fit(ranges: Sequence[float], angle_min: float, angle_increment: float,
        profile: DockProfile, sensor: SensorOffset, now: float) -> ProfileFit:
    """스캔 1장에서 도크 포즈를 찾는다. 절대 예외를 올리지 않는다."""
    wanted = len(profile.post_lateral_m)
    points = _forward_points(ranges, angle_min, angle_increment, profile)
    if len(points) < profile.min_points_per_post * wanted:
        return ProfileFit(reason="too few returns in the forward window",
                          points=len(points))

    clusters = _cluster_by_angular_gap(points, angle_increment)
    if len(clusters) != wanted:
        return ProfileFit(
            reason=f"expected {wanted} clusters, saw {len(clusters)}",
            points=len(points), clusters=len(clusters))
    if any(len(cluster) < profile.min_points_per_post for cluster in clusters):
        return ProfileFit(reason="a cluster is thinner than the minimum",
                          points=len(points), clusters=len(clusters))

    return ProfileFit(reason="pose not implemented yet",
                      points=len(points), clusters=len(clusters))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd src/rosy_core && python -m pytest test/test_dock_profile.py -q`
Expected: PASS, 9 passed

- [ ] **Step 5: Commit**

```bash
git add src/rosy_core/rosy_core/docking/profile.py src/rosy_core/test/test_dock_profile.py
git commit -m 'feat(dock): cluster the scan on angular gaps, which carry no range noise'
```

---

### Task 3: The pose — post centres, Procrustes, and the base_link transform

**Files:**
- Modify: `src/rosy_core/rosy_core/docking/profile.py`
- Modify: `src/rosy_core/test/test_dock_profile.py`

- [ ] **Step 1: Write the failing test**

Append to `src/rosy_core/test/test_dock_profile.py`:

```python
def test_an_exact_scan_recovers_the_pose_in_base_link():
    profile = DockProfile()
    sensor = SensorOffset()
    ranges, angle_min, step = _scan_of_posts(
        profile, 0.500, 0.030, math.radians(8.0), step=STEP_C1)
    got = fit(ranges, angle_min, step, profile, sensor, now=12.5)

    assert got.found is True
    # base_link = sensor frame shifted by the scanner offset
    assert got.observation.x == pytest.approx(0.500 + sensor.x, abs=0.005)
    assert got.observation.y == pytest.approx(0.030, abs=0.003)
    assert got.observation.yaw == pytest.approx(math.radians(8.0), abs=math.radians(3.0))
    assert got.observation.at == 12.5
    assert got.residual_m is not None and got.residual_m < profile.max_residual_m


def test_the_scanner_offset_is_applied_and_not_forgotten():
    profile = DockProfile()
    ranges, angle_min, step = _scan_of_posts(profile, 0.500, 0.0, 0.0, step=STEP_C1)
    zero = fit(ranges, angle_min, step, profile, SensorOffset(0.0, 0.0, 0.0), now=1.0)
    real = fit(ranges, angle_min, step, profile, SensorOffset(), now=1.0)
    assert zero.observation.x - real.observation.x == pytest.approx(0.017, abs=1e-6)


def test_a_layout_that_does_not_match_is_refused_by_the_residual_gate():
    # Three posts really are there, but not at this profile's spacing. The
    # residual is what separates "the dock" from "three things".
    seen = DockProfile(post_lateral_m=(-0.075, -0.015, 0.075))
    ranges, angle_min, step = _scan_of_posts(
        DockProfile(post_lateral_m=(-0.100, 0.010, 0.090)),
        0.500, 0.0, 0.0, step=STEP_C1)
    got = fit(ranges, angle_min, step, seen, SensorOffset(), now=1.0)
    assert got.found is False
    assert "residual" in (got.reason or "")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/rosy_core && python -m pytest test/test_dock_profile.py -q`
Expected: FAIL — `assert got.found is True` fails; reason is still "pose not implemented yet"

- [ ] **Step 3: Implement the pose**

In `src/rosy_core/rosy_core/docking/profile.py`, add these helpers above `fit`:

```python
#: 반지름 r 원통의 보이는 앞면에서 거리는 중심에서 d-r(정면)부터 d(가장자리)까지
#: 변하고, 호 전체 평균은 d - (π/4)r 이다. 그래서 평균에 이 값을 되돌려 더한다.
_ARC_MEAN_BIAS = math.pi / 4.0


def _post_centre(cluster: list[tuple[float, float]],
                 radius: float) -> tuple[float, float]:
    """중심 = (방위각 평균, 거리 평균 + (π/4)·반지름).

    **최솟값이 아니라 평균을 쓴다.** 최솟값은 잡음 표본 중 가장 나쁜 것을 고르는
    추정기다. σ = 20 mm 에서 최솟값을 쓰면 정상 도크의 residual 이 최대 29.4 mm
    까지 벌어져 간격이 어긋난 배치(21.8 mm)와 겹치고, 그 순간 게이트로 둘을
    가를 수 없게 된다. 평균은 √N 만큼 잡음을 줄여 최악 13.0 mm 로 내리고,
    횡오차도 2.52 → 0.87 mm 로 함께 좋아진다.

    방위각은 언제나 평균이다 — 거리 잡음이 여기에는 들어오지 않고, 이 추정기의
    횡 정밀도가 거기서 나온다.
    """
    bearing = sum(item[0] for item in cluster) / len(cluster)
    mean_range = sum(item[1] for item in cluster) / len(cluster)
    distance = mean_range + _ARC_MEAN_BIAS * radius
    return (distance * math.cos(bearing), distance * math.sin(bearing))


def _procrustes(model: list[tuple[float, float]],
                observed: list[tuple[float, float]]
                ) -> tuple[float, float, float, float]:
    """관측 중심들을 알려진 배치에 회전+평행이동으로 맞춘다.

    돌려주는 것은 (yaw, tx, ty, rms residual). 도크 원점은 모델의 (0, 0) 이므로
    평행이동이 곧 도크 원점의 센서 프레임 좌표다 — 관측 중심의 평균이 아니다.
    """
    count = len(model)
    mcx = sum(item[0] for item in model) / count
    mcy = sum(item[1] for item in model) / count
    ocx = sum(item[0] for item in observed) / count
    ocy = sum(item[1] for item in observed) / count

    numerator = denominator = 0.0
    for (mx, my), (ox, oy) in zip(model, observed):
        ax, ay = mx - mcx, my - mcy
        bx, by = ox - ocx, oy - ocy
        numerator += ax * by - ay * bx
        denominator += ax * bx + ay * by
    yaw = math.atan2(numerator, denominator)

    cos_y, sin_y = math.cos(yaw), math.sin(yaw)
    tx = ocx - (cos_y * mcx - sin_y * mcy)
    ty = ocy - (sin_y * mcx + cos_y * mcy)

    total = 0.0
    for (mx, my), (ox, oy) in zip(model, observed):
        px = cos_y * mx - sin_y * my + tx
        py = sin_y * mx + cos_y * my + ty
        total += (px - ox) ** 2 + (py - oy) ** 2
    return yaw, tx, ty, math.sqrt(total / count)


def _to_base_link(x: float, y: float, yaw: float,
                  sensor: SensorOffset) -> tuple[float, float, float]:
    """센서 프레임 포즈를 `base_link` 로 옮긴다.

    이 변환이 경계 안에 있는 이유: `DockObservation` 의 계약이 `base_link` 다.
    호출자에게 맡기면 언젠가 한 곳이 빼먹고, 그 결과는 17 mm 만큼 가깝다고
    믿는 로봇이다.
    """
    cos_s, sin_s = math.cos(sensor.yaw), math.sin(sensor.yaw)
    return (sensor.x + cos_s * x - sin_s * y,
            sensor.y + sin_s * x + cos_s * y,
            _wrap(sensor.yaw + yaw))
```

Then replace the final `return ProfileFit(reason="pose not implemented yet", ...)`
in `fit` with:

```python
    observed = [_post_centre(cluster, profile.post_radius_m)
                for cluster in clusters]
    # 대응은 방위각 순서로 성립한다 — 방위각이 오르면 횡좌표도 오른다.
    model = [(0.0, lateral) for lateral in sorted(profile.post_lateral_m)]
    yaw, tx, ty, residual = _procrustes(model, observed)
    if residual > profile.max_residual_m:
        return ProfileFit(
            reason=f"residual {residual:.4f} m over {profile.max_residual_m:.4f} m",
            residual_m=residual, points=len(points), clusters=len(clusters))

    bx, by, byaw = _to_base_link(tx, ty, yaw, sensor)
    return ProfileFit(
        observation=DockObservation(
            x=bx, y=by, yaw=byaw,
            confidence=max(0.0, 1.0 - residual / profile.max_residual_m),
            at=now),
        residual_m=residual, points=len(points), clusters=len(clusters))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd src/rosy_core && python -m pytest test/test_dock_profile.py -q`
Expected: PASS, 12 passed

- [ ] **Step 5: Commit**

```bash
git add src/rosy_core/rosy_core/docking/profile.py src/rosy_core/test/test_dock_profile.py
git commit -m 'feat(dock): produce the base_link pose the observation contract asks for'
```

---

### Task 4: Pin the property the shape was chosen for

The design picked posts over a V because their lateral error is set by bearing
quantisation, not range noise. That is a claim about behaviour, so it becomes a
test — otherwise a later "improvement" that starts averaging ranges silently
throws the reason away.

**Files:**
- Modify: `src/rosy_core/test/test_dock_profile.py`

- [ ] **Step 1: Write the failing test**

Append to `src/rosy_core/test/test_dock_profile.py`:

```python
def _lateral_rms(sigma, trials=200, step=STEP_SIM, seed=11):
    profile = DockProfile()
    sensor = SensorOffset()
    rng = random.Random(seed)
    errors, misses = [], 0
    for trial in range(trials):
        x = rng.uniform(0.25, 0.70)
        y = rng.uniform(-0.06, 0.06)
        yaw = math.radians(rng.uniform(-15.0, 15.0))
        ranges, angle_min, increment = _scan_of_posts(
            profile, x, y, yaw, step=step, sigma=sigma, seed=trial)
        got = fit(ranges, angle_min, increment, profile, sensor, now=float(trial))
        if not got.found:
            misses += 1
            continue
        errors.append(got.observation.y - y)
    rms = math.sqrt(sum(e * e for e in errors) / len(errors)) if errors else math.inf
    return rms, misses, trials


def test_the_lateral_budget_holds_at_the_noise_the_simulator_declares():
    # Gazebo declares sigma = 20 mm, which is worse than the real C1. The gate
    # is 10 mm, so passing here means passing without knowing the C1 number.
    # Measured: 0.87 mm RMS, 0 misses out of 200.
    rms, misses, trials = _lateral_rms(0.020)
    assert misses == 0, f"{misses}/{trials} scans produced no fit"
    assert rms <= 0.010, f"lateral RMS {rms * 1000:.2f} mm over the 10 mm gate"


def test_lateral_accuracy_barely_moves_when_range_noise_drops_sixfold():
    # This is the whole reason posts beat the V. If a change makes lateral
    # accuracy track sigma, the shape decision no longer holds and this fails.
    # Measured ratio 1.46; the bound is 2.0 so the test is not a coin flip.
    coarse, _, _ = _lateral_rms(0.020)
    fine, _, _ = _lateral_rms(0.0035)
    assert coarse / fine < 2.0, (
        f"lateral RMS moved {coarse / fine:.2f}x with sigma; "
        "the estimator has started depending on range noise")


def test_the_residual_gate_separates_a_noisy_right_dock_from_a_wrong_layout():
    """The gate only means something if it sits between the two populations.

    Measured: noisy-correct worst 13.0 mm over 400 trials, wrong-layout
    21.8 mm with no noise at all, gate 18 mm. Squeeze either side and the
    gate stops being able to do both jobs — which is exactly what happened
    with the first estimator that took the minimum range.
    """
    profile = DockProfile()
    sensor = SensorOffset()
    rng = random.Random(5)
    worst = 0.0
    for trial in range(400):
        x = rng.uniform(0.25, 0.70)
        y = rng.uniform(-0.06, 0.06)
        yaw = math.radians(rng.uniform(-15.0, 15.0))
        ranges, angle_min, increment = _scan_of_posts(
            profile, x, y, yaw, step=STEP_SIM, sigma=0.020, seed=1000 + trial)
        got = fit(ranges, angle_min, increment, profile, sensor, now=0.0)
        assert got.found, f"the gate rejected a real dock: {got.reason}"
        worst = max(worst, got.residual_m)

    ranges, angle_min, increment = _scan_of_posts(
        DockProfile(post_lateral_m=(-0.100, 0.010, 0.090)),
        0.500, 0.0, 0.0, step=STEP_C1)
    wrong = fit(ranges, angle_min, increment, profile, sensor, now=0.0)
    assert wrong.found is False
    assert worst < profile.max_residual_m < wrong.residual_m, (
        f"gate {profile.max_residual_m * 1000:.0f} mm no longer sits between "
        f"noisy-correct {worst * 1000:.1f} mm and wrong-layout "
        f"{wrong.residual_m * 1000:.1f} mm")
```

- [ ] **Step 2: Run the tests**

Run: `cd src/rosy_core && python -m pytest test/test_dock_profile.py -q`
Expected: PASS, 15 passed. If the noise or separation test fails, the estimator
regressed — fix the estimator, do not relax the gate.

- [ ] **Step 3: Commit**

```bash
git add src/rosy_core/test/test_dock_profile.py
git commit -m 'test(dock): pin the noise independence that chose posts over a V face' \
           -m 'And pin the residual gate between the two populations it has to
separate. The first estimator took the minimum range per post, which is a
picker of the worst noise sample: at sigma = 20 mm it pushed a correct dock
to 29.4 mm residual while a wrong layout sat at 21.8 mm, so no threshold
could do both jobs. Averaging the arc and correcting by (pi/4)r drops the
worst correct case to 13.0 mm.'

---

### Task 5: The row and its CSV round trip

**Files:**
- Create: `src/rosy_core/rosy_core/docking/probe.py`
- Create: `src/rosy_core/test/test_dock_probe.py`

- [ ] **Step 1: Write the failing test**

```python
"""Probe rows and the verdict that picks a detector (design: 2026-09-07 rig)."""

from __future__ import annotations

import math

from rosy_core.docking.probe import FIELDS, ProbeRow, append_row, read_rows


def test_the_schema_is_one_table_for_all_three_candidates():
    # Splitting the CSV per candidate splits the verdict into three, and at
    # that moment the candidates stop being comparable.
    assert FIELDS[:3] == ("lane", "candidate", "dock_present")
    for name in ("fit_y", "int_target", "int_baseline", "ir_l", "ir_r", "ambient"):
        assert name in FIELDS


def test_a_row_round_trips_through_csv_with_blanks_preserved(tmp_path):
    path = tmp_path / "rows.csv"
    geometry = ProbeRow(lane="sim", candidate="geometry", truth_x=0.7,
                        truth_y=0.02, truth_yaw=0.0, fit_x=0.68, fit_y=0.021,
                        fit_yaw=0.01, residual=0.002, points=22, confidence=0.8)
    infrared = ProbeRow(lane="bench", candidate="ir", truth_x=0.04,
                        truth_y=-0.01, truth_yaw=0.0, ambient="direct-sun",
                        ir_l=812, ir_mid=903, ir_r=511)
    append_row(path, geometry)
    append_row(path, infrared)

    back = read_rows(path)
    assert len(back) == 2
    assert back[0].fit_y == 0.021
    assert back[0].ir_l is None          # blank stays blank, not zero
    assert back[1].ambient == "direct-sun"
    assert back[1].fit_x is None
    assert back[1].ir_mid == 903


def test_the_header_is_written_once(tmp_path):
    path = tmp_path / "rows.csv"
    for index in range(3):
        append_row(path, ProbeRow(lane="sim", candidate="geometry",
                                  truth_x=0.5, truth_y=0.0, truth_yaw=0.0,
                                  fit_x=0.48, fit_y=0.001))
    assert path.read_text(encoding="utf-8").count("truth_x") == 1
    assert len(read_rows(path)) == 3


def test_a_dock_absent_row_is_explicit_rather_than_a_missing_truth(tmp_path):
    # False positives are the strongest criterion, so "there was no dock" has
    # to be a stated fact and not an empty cell that could mean anything.
    path = tmp_path / "rows.csv"
    append_row(path, ProbeRow(lane="sim", candidate="geometry",
                              dock_present=False, truth_x=math.nan,
                              truth_y=math.nan, truth_yaw=math.nan))
    back = read_rows(path)
    assert back[0].dock_present is False
    assert math.isnan(back[0].truth_x)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/rosy_core && python -m pytest test/test_dock_probe.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'rosy_core.docking.probe'`

- [ ] **Step 3: Implement the row and the CSV layer**

Create `src/rosy_core/rosy_core/docking/probe.py`:

```python
"""rosy_core.docking.probe — 측정 기록과, 감지 방식을 고르는 판정.

**두 갈래가 같은 표를 쓰고 같은 판정을 통과한다.** Gazebo 스윕과 실기 벤치가
각자 CSV 를 쓰면 판정이 셋으로 갈라지고, 그 순간 후보들이 비교 불가능해진다.
해당 없는 칸은 빈칸으로 남고, 빈칸은 0 이 아니다.

판정 기준의 숫자는 측정 *전에* 정해졌다. 측정 후에 기준을 정하면 원하는 답이
나온다. 그래서 상수가 이 파일 맨 위에 있고 설계 문서와 같은 값이다.

ROS 무의존 — 이 파일이 감지 방식을 고르는 결정을 소유하므로, host pytest 가
그것을 볼 수 있어야 한다(criterion C1).

설계: docs/plans/2026-09-07-dock-detector-measurement-rig-design.md
"""

from __future__ import annotations

import csv
import math
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

#: 스테이징 획득률을 재는 거리 띠.
STAGING_BAND_M = (0.65, 0.75)
ACQUIRE_RATE_MIN = 0.95
#: 깔때기가 ±20 mm 를 흡수하므로 여유 2배.
LATERAL_RMS_MAX_M = 0.010
GATE_RANGE_MAX_M = 0.70
ENVELOPE_BIN_M = 0.05
#: IR 단조성을 보는 횡 밴드, 그리고 순서가 맞아야 하는 인접쌍 비율.
IR_BAND_M = 0.020
IR_MONOTONIC_MIN = 0.80
#: 응답 시작 거리가 이보다 짧으면 접점 판정에 쓸 수 없다
#: (`DockType.docking_threshold_m` 기본값과 같은 숫자).
IR_ONSET_MIN_M = 0.05


FIELDS = ("lane", "candidate", "dock_present", "truth_x", "truth_y",
          "truth_yaw", "ambient", "fit_x", "fit_y", "fit_yaw", "residual",
          "points", "confidence", "int_target", "int_baseline",
          "ir_l", "ir_mid", "ir_r")


@dataclass(frozen=True)
class ProbeRow:
    """표본 하나. 후보와 무관한 칸은 `None` 으로 남는다."""

    lane: str
    candidate: str
    truth_x: float
    truth_y: float
    truth_yaw: float
    dock_present: bool = True
    ambient: str = ""
    fit_x: Optional[float] = None
    fit_y: Optional[float] = None
    fit_yaw: Optional[float] = None
    residual: Optional[float] = None
    points: Optional[int] = None
    confidence: Optional[float] = None
    int_target: Optional[float] = None
    int_baseline: Optional[float] = None
    ir_l: Optional[int] = None
    ir_mid: Optional[int] = None
    ir_r: Optional[int] = None


_INT_FIELDS = frozenset({"points", "ir_l", "ir_mid", "ir_r"})
_FLOAT_FIELDS = frozenset({"truth_x", "truth_y", "truth_yaw", "fit_x", "fit_y",
                           "fit_yaw", "residual", "confidence", "int_target",
                           "int_baseline"})


def _encode(row: ProbeRow) -> dict[str, str]:
    raw = asdict(row)
    out: dict[str, str] = {}
    for name in FIELDS:
        value = raw[name]
        if value is None:
            out[name] = ""
        elif isinstance(value, bool):
            out[name] = "1" if value else "0"
        else:
            out[name] = str(value)
    return out


def _decode(record: dict[str, str]) -> ProbeRow:
    kwargs: dict[str, Any] = {}
    for field in fields(ProbeRow):
        text = (record.get(field.name) or "").strip()
        if field.name == "dock_present":
            # 빈칸은 dataclass 기본값(True)과 같게 읽는다. 손으로 쓴 CSV 에서
            # 칸이 비었다고 "도크가 없었다"로 뒤집히면 거짓 양성 집계가 조용히
            # 부풀어 통과할 후보를 떨어뜨린다.
            kwargs[field.name] = text not in ("0", "false", "False")
        elif field.name in ("lane", "candidate", "ambient"):
            kwargs[field.name] = text
        elif text == "":
            # 필수 진실값이 비었으면 NaN 이다 — 0 으로 채우면 도크가 로봇 위에
            # 있다는 뜻이 되어 판정이 조용히 틀린다.
            kwargs[field.name] = math.nan if field.name.startswith("truth") else None
        elif field.name in _INT_FIELDS:
            kwargs[field.name] = int(float(text))
        elif field.name in _FLOAT_FIELDS:
            kwargs[field.name] = float(text)
        else:
            kwargs[field.name] = text
    return ProbeRow(**kwargs)


def append_row(path: Path, row: ProbeRow) -> None:
    """한 줄 붙이고 즉시 flush 한다.

    스윕이 중간에 죽으면 비싼 물리 실험이 날아간다. 앞선 줄은 남아야 한다.
    """
    target = Path(path)
    fresh = not target.exists() or target.stat().st_size == 0
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(FIELDS))
        if fresh:
            writer.writeheader()
        writer.writerow(_encode(row))
        handle.flush()


def read_rows(path: Path) -> list[ProbeRow]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return [_decode(record) for record in csv.DictReader(handle)]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd src/rosy_core && python -m pytest test/test_dock_probe.py -q`
Expected: PASS, 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/rosy_core/rosy_core/docking/probe.py src/rosy_core/test/test_dock_probe.py
git commit -m 'feat(dock): give both measurement lanes one table, with blanks that stay blank'
```

---

### Task 6: The geometry verdict

**Files:**
- Modify: `src/rosy_core/rosy_core/docking/probe.py`
- Modify: `src/rosy_core/test/test_dock_probe.py`

- [ ] **Step 1: Write the failing test**

Append to `src/rosy_core/test/test_dock_probe.py`:

```python
from rosy_core.docking.probe import ProbeVerdict, verdict


def _geometry_rows(lateral_error=0.002, acquired=True, count=40):
    rows = []
    for index in range(count):
        truth_x = 0.70 - index * 0.005          # 0.70 down to 0.505
        truth_y = 0.01 if index % 2 else -0.01
        rows.append(ProbeRow(
            lane="sim", candidate="geometry", truth_x=truth_x,
            truth_y=truth_y, truth_yaw=0.0,
            fit_x=truth_x if acquired else None,
            fit_y=(truth_y + lateral_error) if acquired else None,
            fit_yaw=0.0 if acquired else None,
            residual=0.001, points=22, confidence=0.9))
    return rows


def _absent_rows(false_positives=0, count=20):
    rows = []
    for index in range(count):
        hit = index < false_positives
        rows.append(ProbeRow(
            lane="sim", candidate="geometry", dock_present=False,
            truth_x=math.nan, truth_y=math.nan, truth_yaw=math.nan,
            fit_x=0.5 if hit else None, fit_y=0.0 if hit else None))
    return rows


def test_a_clean_geometry_sweep_passes():
    got = verdict(_geometry_rows() + _absent_rows())
    assert len(got) == 1
    assert got[0].candidate == "geometry"
    assert got[0].passed is True, got[0].reasons
    assert got[0].metrics["lateral_rms_m"] < LATERAL_RMS_MAX_M


def test_lateral_error_over_the_gate_fails_and_says_so():
    got = verdict(_geometry_rows(lateral_error=0.018) + _absent_rows())
    assert got[0].passed is False
    assert any("lateral" in reason for reason in got[0].reasons)


def test_one_false_positive_fails_the_candidate():
    # Zero is the criterion. One confident wrong pose drives the robot into
    # something that is not the dock.
    got = verdict(_geometry_rows() + _absent_rows(false_positives=1))
    assert got[0].passed is False
    assert any("false positive" in reason for reason in got[0].reasons)
    assert got[0].metrics["false_positives"] == 1.0


def test_no_dock_absent_samples_is_a_failure_not_a_pass():
    # A sweep that never looked at an empty room has not tested the criterion.
    got = verdict(_geometry_rows())
    assert got[0].passed is False
    assert any("false positive" in reason for reason in got[0].reasons)


def test_a_sweep_that_never_acquires_fails_on_the_rate():
    got = verdict(_geometry_rows(acquired=False) + _absent_rows())
    assert got[0].passed is False
    assert got[0].metrics["acquire_rate"] == 0.0


def test_the_usable_envelope_lower_bound_is_reported():
    rows = _geometry_rows() + _absent_rows()
    # Everything closer than 0.30 m fails to acquire, which is what a real
    # envelope looks like: the posts leave the field of view.
    for index in range(30):
        truth_x = 0.30 - index * 0.008
        rows.append(ProbeRow(lane="sim", candidate="geometry", truth_x=truth_x,
                             truth_y=0.0, truth_yaw=0.0))
    got = verdict(rows)
    assert got[0].metrics["envelope_low_m"] >= 0.30
```

Also add `LATERAL_RMS_MAX_M` to the imports at the top of the test file.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/rosy_core && python -m pytest test/test_dock_probe.py -q`
Expected: FAIL — `ImportError: cannot import name 'ProbeVerdict'`

- [ ] **Step 3: Implement the verdict and its geometry arm**

Append to `src/rosy_core/rosy_core/docking/probe.py`:

```python
@dataclass(frozen=True)
class ProbeVerdict:
    """후보 하나에 대한 판정. `reasons` 가 비면 통과다."""

    candidate: str
    passed: bool
    reasons: tuple[str, ...]
    metrics: dict[str, float]


def verdict(rows: Iterable[ProbeRow]) -> tuple[ProbeVerdict, ...]:
    """표에 등장한 후보마다 판정을 낸다. 순서는 후보 이름 순이다."""
    collected = list(rows)
    arms = {"geometry": _verdict_geometry,
            "intensity": _verdict_intensity,
            "ir": _verdict_ir}
    out = []
    for name in sorted({row.candidate for row in collected}):
        arm = arms.get(name)
        if arm is None:
            out.append(ProbeVerdict(name, False, ("unknown candidate",), {}))
            continue
        out.append(arm([row for row in collected if row.candidate == name]))
    return tuple(out)


def _rate(rows: Sequence[ProbeRow]) -> float:
    if not rows:
        return 0.0
    return sum(1 for row in rows if row.fit_x is not None) / len(rows)


def _envelope_low(rows: Sequence[ProbeRow]) -> float:
    """획득률이 기준 위로 유지되는 연속 구간의 하단.

    하단을 가정하지 않고 재는 이유: 접점 직전 수 cm 에서 기둥은 시야를 벗어난다.
    그 하단이 `docking_threshold_m` 에 못 미치면 기종 설정으로 흡수한다.
    """
    binned: dict[int, list[ProbeRow]] = {}
    for row in rows:
        if not math.isfinite(row.truth_x):
            continue
        binned.setdefault(round(row.truth_x / ENVELOPE_BIN_M), []).append(row)
    good = sorted(key for key, items in binned.items()
                  if _rate(items) >= ACQUIRE_RATE_MIN)
    if not good:
        return math.nan
    low = good[-1]
    for key in reversed(good):
        if low - key <= 1:
            low = key
        else:
            break
    return low * ENVELOPE_BIN_M


def _verdict_geometry(rows: Sequence[ProbeRow]) -> ProbeVerdict:
    present = [row for row in rows if row.dock_present]
    absent = [row for row in rows if not row.dock_present]
    reasons: list[str] = []
    metrics: dict[str, float] = {}

    staging = [row for row in present
               if math.isfinite(row.truth_x)
               and STAGING_BAND_M[0] <= row.truth_x <= STAGING_BAND_M[1]]
    rate = _rate(staging)
    metrics["acquire_rate"] = rate
    if not staging:
        reasons.append("no samples inside the staging band")
    elif rate < ACQUIRE_RATE_MIN:
        reasons.append(f"acquisition {rate:.1%} below {ACQUIRE_RATE_MIN:.0%}")

    gated = [row for row in present
             if row.fit_y is not None and math.isfinite(row.truth_x)
             and row.truth_x <= GATE_RANGE_MAX_M]
    if not gated:
        metrics["lateral_rms_m"] = math.inf
        reasons.append("no fits inside the gate window")
    else:
        rms = math.sqrt(sum((row.fit_y - row.truth_y) ** 2
                            for row in gated) / len(gated))
        metrics["lateral_rms_m"] = rms
        if rms > LATERAL_RMS_MAX_M:
            reasons.append(
                f"lateral RMS {rms * 1000:.1f} mm over "
                f"{LATERAL_RMS_MAX_M * 1000:.0f} mm")

    hits = sum(1 for row in absent if row.fit_x is not None)
    metrics["false_positives"] = float(hits)
    if not absent:
        reasons.append("no dock-absent samples, so false positives are untested")
    elif hits:
        reasons.append(f"{hits} false positive(s)")

    metrics["envelope_low_m"] = _envelope_low(present)
    return ProbeVerdict("geometry", not reasons, tuple(reasons), metrics)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd src/rosy_core && python -m pytest test/test_dock_probe.py -q`
Expected: PASS, 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/rosy_core/rosy_core/docking/probe.py src/rosy_core/test/test_dock_probe.py
git commit -m 'feat(dock): fail the geometry candidate on one false positive, and on an untested one'
```

---

### Task 7: The intensity and IR verdicts

**Files:**
- Modify: `src/rosy_core/rosy_core/docking/probe.py`
- Modify: `src/rosy_core/test/test_dock_probe.py`

- [ ] **Step 1: Write the failing test**

Append to `src/rosy_core/test/test_dock_probe.py`:

```python
def _intensity_rows(target=200.0, baseline=40.0, count=12):
    return [ProbeRow(lane="bench", candidate="intensity",
                     truth_x=0.2 + index * 0.05, truth_y=0.0, truth_yaw=0.0,
                     int_target=target, int_baseline=baseline)
            for index in range(count)]


def test_separated_intensity_passes():
    got = verdict(_intensity_rows())
    assert got[0].candidate == "intensity"
    assert got[0].passed is True, got[0].reasons


def test_a_constant_intensity_field_fails_the_candidate():
    # The rviz snapshot in the tree shows min == max == 47, so this is the
    # outcome the design expects if sllidar reports quality and not reflectance.
    got = verdict(_intensity_rows(target=47.0, baseline=47.0))
    assert got[0].passed is False
    assert any("overlap" in reason for reason in got[0].reasons)


def _ir_rows(band="indoor", monotonic=True, onset_x=0.12):
    rows = []
    # ambient floor, measured with no dock in front of the sensors
    for index in range(4):
        rows.append(ProbeRow(lane="bench", candidate="ir", dock_present=False,
                             truth_x=math.nan, truth_y=math.nan,
                             truth_yaw=math.nan, ambient=band,
                             ir_l=100, ir_mid=100, ir_r=100))
    for index in range(9):
        lateral = -0.020 + index * 0.005
        skew = int(lateral * 20000) if monotonic else 0
        # The dock to the robot's left (+y) lights the left channel more, so
        # (ir_l - ir_r) must RISE with truth_y. Getting this sign backwards is
        # what a real wiring swap looks like, and the verdict has to catch it.
        rows.append(ProbeRow(lane="bench", candidate="ir", truth_x=0.03,
                             truth_y=lateral, truth_yaw=0.0, ambient=band,
                             ir_l=600 + skew, ir_mid=800, ir_r=600 - skew))
    rows.append(ProbeRow(lane="bench", candidate="ir", truth_x=onset_x,
                         truth_y=0.0, truth_yaw=0.0, ambient=band,
                         ir_l=140, ir_mid=180, ir_r=140))
    return rows


def test_a_monotonic_ir_skew_passes():
    got = verdict(_ir_rows())
    assert got[0].candidate == "ir"
    assert got[0].passed is True, got[0].reasons
    assert got[0].metrics["onset_m_indoor"] >= 0.12


def test_a_flat_ir_skew_fails_because_it_cannot_tell_left_from_right():
    got = verdict(_ir_rows(monotonic=False))
    assert got[0].passed is False
    assert any("monotonic" in reason for reason in got[0].reasons)


def test_an_onset_inside_the_contact_tolerance_fails():
    got = verdict(_ir_rows(onset_x=0.02))
    assert got[0].passed is False
    assert any("onset" in reason for reason in got[0].reasons)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/rosy_core && python -m pytest test/test_dock_probe.py -q`
Expected: FAIL — the intensity rows return `ProbeVerdict("intensity", False, ("unknown candidate",), {})`

- [ ] **Step 3: Implement both arms**

Append to `src/rosy_core/rosy_core/docking/probe.py`:

```python
def _verdict_intensity(rows: Sequence[ProbeRow]) -> ProbeVerdict:
    """역반사와 무광이 모든 거리에서 갈라지는가.

    겹치면 탈락이다. 부분적으로만 갈라지는 intensity 로는 임계를 하나 고를 수
    없고, 거리에 따라 임계를 바꾸는 것은 감지기가 아니라 추측이다.
    """
    usable = [row for row in rows
              if row.int_target is not None and row.int_baseline is not None
              and math.isfinite(row.truth_x)]
    if not usable:
        return ProbeVerdict("intensity", False,
                            ("no rows carry both a target and a baseline",), {})

    binned: dict[int, list[ProbeRow]] = {}
    for row in usable:
        binned.setdefault(round(row.truth_x / ENVELOPE_BIN_M), []).append(row)

    reasons: list[str] = []
    worst = math.inf
    for key in sorted(binned):
        items = binned[key]
        margin = (min(row.int_target for row in items)
                  - max(row.int_baseline for row in items))
        worst = min(worst, margin)
        if margin <= 0.0:
            reasons.append(
                f"retro and matte overlap at {key * ENVELOPE_BIN_M:.2f} m "
                f"(margin {margin:.1f})")
    return ProbeVerdict("intensity", not reasons, tuple(reasons),
                        {"worst_margin": worst})


def _verdict_ir(rows: Sequence[ProbeRow]) -> ProbeVerdict:
    """`ir_l - ir_r` 이 접점 밴드에서 좌우를 가르는가, 그리고 언제부터 응답하는가.

    주변광 구간마다 따로 본다. 판정을 가르는 것은 가장 밝은 구간이다 — 밝은
    곳에서 무너지는 감지기는 창가에 놓인 도크에서 쓸 수 없다.
    """
    reasons: list[str] = []
    metrics: dict[str, float] = {}
    bands = sorted({row.ambient for row in rows if row.ambient})
    if not bands:
        return ProbeVerdict("ir", False, ("no ambient band recorded",), {})

    for band in bands:
        in_band = [row for row in rows if row.ambient == band]
        floor = max((max(value for value in (row.ir_l, row.ir_mid, row.ir_r)
                         if value is not None)
                     for row in in_band
                     if not row.dock_present
                     and any(value is not None
                             for value in (row.ir_l, row.ir_mid, row.ir_r))),
                    default=None)
        if floor is None:
            reasons.append(f"{band}: no dock-absent rows to set the ambient floor")
            continue

        skewed = sorted(
            (row for row in in_band
             if row.dock_present and row.ir_l is not None and row.ir_r is not None
             and math.isfinite(row.truth_y) and abs(row.truth_y) <= IR_BAND_M),
            key=lambda row: row.truth_y)
        if len(skewed) < 3:
            reasons.append(f"{band}: fewer than three samples inside the band")
        else:
            pairs = list(zip(skewed, skewed[1:]))
            ordered = sum(1 for a, b in pairs
                          if (b.ir_l - b.ir_r) > (a.ir_l - a.ir_r))
            share = ordered / len(pairs)
            metrics[f"monotonic_{band}"] = share
            if share < IR_MONOTONIC_MIN:
                reasons.append(
                    f"{band}: skew monotonic in only {share:.0%} of pairs, "
                    f"under {IR_MONOTONIC_MIN:.0%}")

        responded = [row.truth_x for row in in_band
                     if row.dock_present and math.isfinite(row.truth_x)
                     and max((value for value in (row.ir_l, row.ir_mid, row.ir_r)
                              if value is not None), default=0) > floor]
        onset = max(responded) if responded else 0.0
        metrics[f"onset_m_{band}"] = onset
        if onset < IR_ONSET_MIN_M:
            reasons.append(
                f"{band}: onset {onset * 1000:.0f} mm inside the "
                f"{IR_ONSET_MIN_M * 1000:.0f} mm contact tolerance")

    return ProbeVerdict("ir", not reasons, tuple(reasons), metrics)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd src/rosy_core && python -m pytest test/test_dock_probe.py -q`
Expected: PASS, 15 passed

- [ ] **Step 5: Run the whole docking suite plus the criteria guard**

Run: `cd src/rosy_core && python -m pytest test/test_docking.py test/test_dock_profile.py test/test_dock_probe.py test/test_module_criteria.py -q`
Expected: PASS, 131 passed (100 + 15 + 15 + 1). `test_module_criteria.py` must
stay green — neither new module may use `hasattr` or `getattr`.

- [ ] **Step 6: Commit**

```bash
git add src/rosy_core/rosy_core/docking/probe.py src/rosy_core/test/test_dock_probe.py
git commit -m 'feat(dock): judge intensity on overlap and IR on the brightest band'
```

---

### Task 8: The measurement dock in Gazebo

**Files:**
- Create: `src/rosy_gz_sim/models/dock/model.sdf`
- Create: `src/rosy_gz_sim/models/dock/model.config`

Posts must stand through the scan plane, which sits 95 mm above the floor
(`base_link` is 28 mm up, `rplidar_link` 67 mm above that). A 110 mm post
clears it with margin and matches the minimum dock height the design derived.

- [ ] **Step 1: Write the model config**

Create `src/rosy_gz_sim/models/dock/model.config`:

```xml
<?xml version="1.0"?>
<model>
  <name>dock</name>
  <version>1.0</version>
  <sdf version="1.9">model.sdf</sdf>
  <description>
    Measurement dock for the detector rig: three asymmetric posts that stand
    through the 95 mm scan plane, plus a base plate. Shape only -- the
    mechanical funnel and contacts are out of this cycle's scope.

    The robot approaches the dock's -x face, so the model's axes are already
    aligned with the robot's when the dock's world yaw is zero. Do not place it
    rotated by pi: that mirrors the lateral axis and flips the asymmetric post
    pattern the detector matches against.
  </description>
</model>
```

- [ ] **Step 2: Write the model**

Create `src/rosy_gz_sim/models/dock/model.sdf`:

```xml
<?xml version="1.0"?>
<sdf version="1.9">
  <model name="dock">
    <static>true</static>
    <link name="body">
      <!-- Base plate. Below the scan plane, so it contributes no returns. -->
      <visual name="plate_visual">
        <pose>0.03 0 0.005 0 0 0</pose>
        <geometry><box><size>0.10 0.20 0.01</size></box></geometry>
      </visual>
      <collision name="plate_collision">
        <pose>0.03 0 0.005 0 0 0</pose>
        <geometry><box><size>0.10 0.20 0.01</size></box></geometry>
      </collision>

      <!-- Three posts at -75 / -15 / +75 mm. The asymmetry is what gives yaw
           a sign and what an accidental pair of furniture legs cannot fake. -->
      <visual name="post_l_visual">
        <pose>0 -0.075 0.055 0 0 0</pose>
        <geometry><cylinder><radius>0.015</radius><length>0.11</length></cylinder></geometry>
      </visual>
      <collision name="post_l_collision">
        <pose>0 -0.075 0.055 0 0 0</pose>
        <geometry><cylinder><radius>0.015</radius><length>0.11</length></cylinder></geometry>
      </collision>

      <visual name="post_m_visual">
        <pose>0 -0.015 0.055 0 0 0</pose>
        <geometry><cylinder><radius>0.015</radius><length>0.11</length></cylinder></geometry>
      </visual>
      <collision name="post_m_collision">
        <pose>0 -0.015 0.055 0 0 0</pose>
        <geometry><cylinder><radius>0.015</radius><length>0.11</length></cylinder></geometry>
      </collision>

      <visual name="post_r_visual">
        <pose>0 0.075 0.055 0 0 0</pose>
        <geometry><cylinder><radius>0.015</radius><length>0.11</length></cylinder></geometry>
      </visual>
      <collision name="post_r_collision">
        <pose>0 0.075 0.055 0 0 0</pose>
        <geometry><cylinder><radius>0.015</radius><length>0.11</length></cylinder></geometry>
      </collision>
    </link>
  </model>
</sdf>
```

- [ ] **Step 3: Verify the model loads**

On a Linux/WSL host with the workspace built:

```bash
colcon build --packages-select rosy_gz_sim
source install/setup.bash
ros2 launch rosy_gz_sim launch_sim.launch.xml
```

Then in a second shell, spawn it 0.7 m in front of the robot:

```bash
ros2 run ros_gz_sim create -world rosy_factory -file \
  "$(ros2 pkg prefix rosy_gz_sim)/share/rosy_gz_sim/models/dock/model.sdf" \
  -name dock -x 0.7 -y 0.0 -z 0.0
```

Expected: three posts visible in the GUI, and `ros2 topic echo /scan --once`
shows a run of returns near 0.7 m in the forward sector.

- [ ] **Step 4: Commit**

```bash
git add src/rosy_gz_sim/models/dock
git commit -m 'feat(sim): stand the measurement dock posts through the 95 mm scan plane'
```

---

### Task 9: The Gazebo sweep

**Files:**
- Create: `src/rosy_gz_sim/scripts/dock_sweep.py`
- Modify: `src/rosy_gz_sim/CMakeLists.txt`

The sweep moves the **dock**, not the robot. Teleporting the robot fights the
diff-drive controller and physics; a static model relocates cleanly. The robot
stays where it spawned, so the dock's world pose is the ground truth after one
fixed transform — and the script verifies the robot has not drifted.

- [ ] **Step 1: Verify the service and topic names on the host**

`gz` CLI names differ across Gazebo versions and cannot be verified from the
dev host. Run this first and use what it prints:

```bash
gz service -l | grep -i set_pose
gz topic -l | grep -i pose
```

Expected: a service named `/world/rosy_factory/set_pose` and a pose topic under
`/world/rosy_factory/`. If the names differ, use the printed ones in Step 2.

- [ ] **Step 2: Write the sweep script**

Create `src/rosy_gz_sim/scripts/dock_sweep.py`:

```python
#!/usr/bin/env python3
"""Gazebo sweep for the dock detector rig.

Moves the dock over a ground-truth grid, samples one scan per pose, runs the
ROS-free fit, and appends a row per sample. The robot never moves: teleporting
it fights the controller, while relocating a static model is exact and free.

Ground truth is exact here, which is the whole reason this lane can afford
hundreds of samples where the bench affords tens.

The grid deliberately runs closer than the 0.70 m gate window. Finding where
the fit stops working IS one of the measurements -- the posts leave the field
of view in the last few centimetres, and that lower bound is not assumed.

Design: docs/plans/2026-09-07-dock-detector-measurement-rig-design.md
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import LaserScan

from rosy_core.docking.probe import ProbeRow, append_row
from rosy_core.docking.profile import DockProfile, SensorOffset, fit

SCAN_QOS = QoSProfile(
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    durability=QoSDurabilityPolicy.VOLATILE,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sweep the dock past the robot and record fit rows.")
    parser.add_argument("--world", default="rosy_factory")
    parser.add_argument("--model", default="dock")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--distances", type=float, nargs="+",
                        default=[0.02, 0.05, 0.08, 0.12, 0.16, 0.20, 0.25,
                                 0.30, 0.40, 0.50, 0.60, 0.68, 0.70, 0.72,
                                 0.85, 1.00])
    parser.add_argument("--laterals", type=float, nargs="+",
                        default=[-0.15, -0.08, -0.03, 0.0, 0.03, 0.08, 0.15])
    parser.add_argument("--yaws-deg", type=float, nargs="+",
                        default=[-20.0, -10.0, 0.0, 10.0, 20.0])
    parser.add_argument("--absent-samples", type=int, default=500,
                        help="scans taken with the dock parked far away")
    parser.add_argument("--park-x", type=float, default=20.0)
    args = parser.parse_args(argv)
    if args.absent_samples < 1:
        parser.error("--absent-samples must be positive")
    return args


def set_dock_pose(world: str, model: str, x: float, y: float,
                  yaw: float) -> None:
    """Relocate the dock. Verified service name comes from Step 1."""
    request = (f'name: "{model}", position: {{x: {x}, y: {y}, z: 0.0}}, '
               f'orientation: {{x: 0.0, y: 0.0, z: {math.sin(yaw / 2.0)}, '
               f'w: {math.cos(yaw / 2.0)}}}')
    subprocess.run(
        ["gz", "service", "-s", f"/world/{world}/set_pose",
         "--reqtype", "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean",
         "--timeout", "2000", "--req", request],
        check=True, capture_output=True, text=True)


class Sweeper(Node):
    def __init__(self) -> None:
        super().__init__("dock_sweep")
        self._scan: LaserScan | None = None
        self.create_subscription(LaserScan, "scan", self._on_scan, SCAN_QOS)

    def _on_scan(self, message: LaserScan) -> None:
        self._scan = message

    def next_scan(self, timeout_s: float = 3.0) -> LaserScan | None:
        self._scan = None
        deadline = self.get_clock().now().nanoseconds + int(timeout_s * 1e9)
        while self.get_clock().now().nanoseconds < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self._scan is not None:
                return self._scan
        return None


def _row(scan, profile, sensor, present, x, y, yaw, now):
    """One row. A scan that produced no fit is a recorded row, not a gap."""
    got = fit(scan.ranges, scan.angle_min, scan.angle_increment,
              profile, sensor, now)
    observation = got.observation
    return ProbeRow(
        lane="sim", candidate="geometry", dock_present=present,
        truth_x=x, truth_y=y, truth_yaw=yaw,
        fit_x=None if observation is None else observation.x,
        fit_y=None if observation is None else observation.y,
        fit_yaw=None if observation is None else observation.yaw,
        residual=got.residual_m, points=got.points,
        confidence=None if observation is None else observation.confidence)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    profile = DockProfile()
    sensor = SensorOffset()

    rclpy.init()
    node = Sweeper()
    written = skipped = 0
    try:
        for distance in args.distances:
            for lateral in args.laterals:
                for yaw_deg in args.yaws_deg:
                    yaw = math.radians(yaw_deg)
                    # World yaw is the truth yaw, NOT pi + yaw. The robot sits
                    # at the origin facing +x and meets the dock's -x face, so
                    # the dock's axes already line up with the world's. Adding
                    # pi mirrors the lateral axis, which flips the asymmetric
                    # post pattern and makes the residual gate reject every
                    # single sample.
                    set_dock_pose(args.world, args.model, distance, lateral, yaw)
                    scan = node.next_scan()
                    if scan is None:
                        skipped += 1
                        continue
                    now = float(written)
                    append_row(args.out, _row(scan, profile, sensor, True,
                                              distance, lateral, yaw, now))
                    written += 1

        set_dock_pose(args.world, args.model, args.park_x, 0.0, 0.0)
        for index in range(args.absent_samples):
            scan = node.next_scan()
            if scan is None:
                skipped += 1
                continue
            append_row(args.out, _row(scan, profile, sensor, False,
                                      math.nan, math.nan, math.nan,
                                      float(written + index)))
            written += 1
    finally:
        node.destroy_node()
        rclpy.shutdown()

    print(f"wrote {written} rows to {args.out}; {skipped} scans timed out")
    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Install the script and declare what it imports**

In `src/rosy_gz_sim/CMakeLists.txt`, immediately before the existing
`install(DIRECTORY ...)` block, add:

```cmake
install(
  PROGRAMS
    scripts/dock_sweep.py
  DESTINATION lib/${PROJECT_NAME}
)
```

The script imports `rosy_core.docking.probe` and `.profile`, and
`rosy_gz_sim` does not depend on `rosy_core` today. An undeclared import works
on a dev machine where everything happens to be sourced and then fails for the
next person, so declare it. In `src/rosy_gz_sim/package.xml`, after the
`<depend>gz_ros2_control</depend>` line, add:

```xml
  <exec_depend>rosy_core</exec_depend>
  <exec_depend>rclpy</exec_depend>
  <exec_depend>sensor_msgs</exec_depend>
```

- [ ] **Step 4: Run the sweep**

```bash
colcon build --packages-select rosy_gz_sim
source install/setup.bash
ros2 launch rosy_gz_sim launch_sim.launch.xml   # shell 1
# shell 2: spawn the dock as in Task 8 Step 3, then
ros2 run rosy_gz_sim dock_sweep.py --out /tmp/dock-sim.csv
```

Expected: `wrote 1060 rows to /tmp/dock-sim.csv; 0 scans timed out`
(560 grid samples plus 500 dock-absent samples).

- [ ] **Step 5: Read the verdict**

```bash
python3 -c "
from pathlib import Path
from rosy_core.docking.probe import read_rows, verdict
for item in verdict(read_rows(Path('/tmp/dock-sim.csv'))):
    print(item.candidate, 'PASS' if item.passed else 'FAIL')
    for reason in item.reasons:
        print('  -', reason)
    for name, value in sorted(item.metrics.items()):
        print(f'  {name} = {value:.4f}')
"
```

Record the printed metrics in the commit message. A FAIL here is a real
result, not a bug to work around: it says the geometric candidate did not
earn the detector slot.

- [ ] **Step 6: Commit**

```bash
git add src/rosy_gz_sim/scripts/dock_sweep.py src/rosy_gz_sim/CMakeLists.txt
git commit -m 'feat(sim): sweep the dock past a stationary robot and record every fit'
```

---

### Task 10: The bench probe

**Files:**
- Create: `src/rosy_bringup/rosy_bringup/dock_probe.py`
- Modify: `src/rosy_bringup/setup.py:26-31`

Shaped after `dynamixel_probe.py`: argparse driven, read-only, and explicit in
its docstring about what it deliberately does not do. This is the tree's first
subscriber to `ir_sensor/range` — until now those three channels were published
and dropped.

- [ ] **Step 1: Write the probe**

Create `src/rosy_bringup/rosy_bringup/dock_probe.py`:

```python
#!/usr/bin/env python3
"""Read-only dock measurement probe.

One invocation captures one sample: the latest `/scan` and `/ir_sensor/range`,
labelled with a ground truth the operator measured with a ruler, appended as
one row to the shared CSV.

The probe never publishes `cmd_vel`, never enables torque, and never commands
the dock. D-2 keeps the Command Manager as the only legal publisher of
`cmd_vel`, and this tool has no reason to be an exception.

A missing message is a recorded blank, not a crash. A sweep that dies halfway
throws away an expensive physical experiment.

Design: docs/plans/2026-09-07-dock-detector-measurement-rig-design.md
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import LaserScan
from std_msgs.msg import UInt16MultiArray

from rosy_core.docking.probe import ProbeRow, append_row
from rosy_core.docking.profile import DockProfile, SensorOffset, fit

BEST_EFFORT = QoSProfile(
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    durability=QoSDurabilityPolicy.VOLATILE,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
)

AMBIENT_BANDS = ("dark", "indoor", "direct-sun")
CANDIDATES = ("geometry", "intensity", "ir")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture one dock measurement row. Reads only.")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--candidate", choices=CANDIDATES, required=True)
    parser.add_argument("--ambient", choices=AMBIENT_BANDS, required=True)
    parser.add_argument("--distance", type=float,
                        help="measured dock distance, m; omit with --no-dock")
    parser.add_argument("--lateral", type=float, default=0.0)
    parser.add_argument("--yaw-deg", type=float, default=0.0)
    parser.add_argument("--no-dock", action="store_true",
                        help="nothing in front: sets the false-positive and "
                             "ambient-floor rows")
    parser.add_argument("--int-target", type=float,
                        help="mean intensity over the retroreflective half")
    parser.add_argument("--int-baseline", type=float,
                        help="mean intensity over the matte half")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args(argv)

    if args.no_dock:
        if args.distance is not None:
            parser.error("--distance makes no sense with --no-dock")
    elif args.distance is None:
        parser.error("--distance is required unless --no-dock is given")
    elif args.distance <= 0.0:
        parser.error("--distance must be positive")

    if args.candidate == "intensity" and not args.no_dock:
        if args.int_target is None or args.int_baseline is None:
            parser.error("the intensity candidate needs both --int-target "
                         "and --int-baseline")
    if args.timeout <= 0.0:
        parser.error("--timeout must be positive")
    return args


class Probe(Node):
    def __init__(self) -> None:
        super().__init__("dock_probe")
        self.scan: LaserScan | None = None
        self.infrared: UInt16MultiArray | None = None
        self.create_subscription(LaserScan, "scan", self._on_scan, BEST_EFFORT)
        self.create_subscription(UInt16MultiArray, "ir_sensor/range",
                                 self._on_ir, BEST_EFFORT)

    def _on_scan(self, message: LaserScan) -> None:
        self.scan = message

    def _on_ir(self, message: UInt16MultiArray) -> None:
        self.infrared = message

    def collect(self, timeout_s: float) -> None:
        deadline = self.get_clock().now().nanoseconds + int(timeout_s * 1e9)
        while self.get_clock().now().nanoseconds < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.scan is not None and self.infrared is not None:
                return


def build_row(args: argparse.Namespace, scan, infrared) -> ProbeRow:
    present = not args.no_dock
    truth_x = math.nan if args.no_dock else args.distance
    truth_y = math.nan if args.no_dock else args.lateral
    truth_yaw = math.nan if args.no_dock else math.radians(args.yaw_deg)

    observation = residual = points = None
    if scan is not None:
        got = fit(scan.ranges, scan.angle_min, scan.angle_increment,
                  DockProfile(), SensorOffset(), now=0.0)
        observation, residual, points = got.observation, got.residual_m, got.points

    channels = list(infrared.data) if infrared is not None else []
    while len(channels) < 3:
        channels.append(None)

    return ProbeRow(
        lane="bench", candidate=args.candidate, dock_present=present,
        truth_x=truth_x, truth_y=truth_y, truth_yaw=truth_yaw,
        ambient=args.ambient,
        fit_x=None if observation is None else observation.x,
        fit_y=None if observation is None else observation.y,
        fit_yaw=None if observation is None else observation.yaw,
        residual=residual, points=points,
        confidence=None if observation is None else observation.confidence,
        int_target=args.int_target, int_baseline=args.int_baseline,
        ir_l=channels[0], ir_mid=channels[1], ir_r=channels[2])


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rclpy.init()
    node = Probe()
    try:
        node.collect(args.timeout)
        if node.scan is None:
            node.get_logger().warn("no scan arrived; recording a blank fit")
        if node.infrared is None:
            node.get_logger().warn("no ir_sensor/range arrived; recording blanks")
        row = build_row(args, node.scan, node.infrared)
        append_row(args.out, row)
        node.get_logger().info(
            f"appended {args.candidate}/{args.ambient} row to {args.out}")
    finally:
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Register the console script**

In `src/rosy_bringup/setup.py`, inside `console_scripts`, after the
`dynamixel_probe` line, add:

```python
            'dock_probe=rosy_bringup.dock_probe:main',
```

- [ ] **Step 3: Verify argument validation on the dev host**

Argument parsing needs no ROS, so it is checkable here:

```bash
cd src/rosy_bringup && python -c "
import sys; sys.argv = ['x']
from rosy_bringup.dock_probe import parse_args
for argv in (['--out','a.csv','--candidate','ir','--ambient','dark'],
             ['--out','a.csv','--candidate','intensity','--ambient','dark','--distance','0.5']):
    try:
        parse_args(argv); print('accepted', argv)
    except SystemExit:
        print('refused ', argv)
"
```

Expected: both lines print `refused` — the first has neither `--distance` nor
`--no-dock`, the second is an intensity capture missing its two intensity
readings. If `rclpy` import fails on this host, run this step on the Pi instead.

- [ ] **Step 4: Commit**

```bash
git add src/rosy_bringup/rosy_bringup/dock_probe.py src/rosy_bringup/setup.py
git commit -m 'feat(bringup): give the tree its first subscriber to ir_sensor/range'
```

---

### Task 11: The bench procedure, and the checklist that owns it

**Files:**
- Create: `deploy/robot/measure-dock-baseline.sh`
- Modify: `docs/deployment/pi5-acceptance-checklist.md` §7.6
- Modify: `src/rosy_core/rosy_core/docking/AGENTS.md`
- Modify: `docs/plans/2026-09-07-dock-detector-measurement-rig-design.md`

- [ ] **Step 1: Write the bench script**

Create `deploy/robot/measure-dock-baseline.sh`, following the shape of
`measure-dds-baseline.sh` — a header that says why the script exists and which
traps a hand-run measurement walks into:

```bash
#!/usr/bin/env bash
# measure-dock-baseline.sh — 도크 감지기 후보 벤치 계측 (ROSY-DOCK-001, D-28)
#
# 사용: ./measure-dock-baseline.sh <출력 CSV> <ambient>
#   ambient: dark | indoor | direct-sun
#
# 이 스크립트가 존재하는 이유: 후보 세 개를 같은 표에 담아야 비교가 되는데,
# 손으로 dock_probe 를 돌리면 캡처마다 라벨이 흔들린다. 아래 함정은 손으로
# 재면 거의 반드시 밟는다.
#
# 함정 1 — intensity 후보는 선행 확인 없이는 측정 자체가 무의미하다.
#   sllidar_ros2 가 C1 에서 `intensities` 를 상수로 채우면 역반사와 무광이
#   갈라질 수가 없다. 저장소의 rviz 스냅샷은 min=max=47 이었다. 그래서 이
#   스크립트는 먼저 그 필드를 찍어 보여주고, 상수로 보이면 경고한다.
#
# 함정 2 — 주변광 라벨을 안 남기면 IR 표본이 쓸모없어진다.
#   IR 은 주변광에 민감하고 판정을 가르는 것은 가장 밝은 구간이다. ambient 를
#   필수 인자로 받는 이유다.
#
# 함정 3 — 도크 없는 표본을 안 찍으면 거짓 양성 기준이 검사되지 않는다.
#   빈 방 표본이 0 개면 판정은 통과가 아니라 FAIL 로 나온다. 이 스크립트가
#   먼저 그것부터 찍는다.

set -euo pipefail

OUT="${1:?출력 CSV 경로가 필요하다}"
AMBIENT="${2:?ambient 구간이 필요하다: dark | indoor | direct-sun}"

case "$AMBIENT" in
  dark|indoor|direct-sun) ;;
  *) echo "알 수 없는 ambient: $AMBIENT" >&2; exit 2 ;;
esac

echo "== 함정 1 확인: /scan 의 intensities =="
timeout 10 ros2 topic echo /scan --field intensities --once \
  | head -c 400 || echo "(intensities 를 읽지 못했다)"
echo
echo "위 값이 모두 같으면 intensity 후보는 측정 없이 탈락이다."
echo

echo "== 도크 없는 표본 (거짓 양성 + 주변광 바닥) =="
for _ in $(seq 1 10); do
  ros2 run rosy_bringup dock_probe --out "$OUT" --candidate geometry \
    --ambient "$AMBIENT" --no-dock
  ros2 run rosy_bringup dock_probe --out "$OUT" --candidate ir \
    --ambient "$AMBIENT" --no-dock
done

cat <<'GUIDE'

== 이제 수동 구간이다 ==
자로 잰 위치마다 아래를 실행한다. 거리는 접점에서 멀어지는 순서로.

  ros2 run rosy_bringup dock_probe --out OUT --candidate geometry \
    --ambient AMBIENT --distance 0.70 --lateral 0.00 --yaw-deg 0

  ros2 run rosy_bringup dock_probe --out OUT --candidate ir \
    --ambient AMBIENT --distance 0.03 --lateral -0.02

  ros2 run rosy_bringup dock_probe --out OUT --candidate intensity \
    --ambient AMBIENT --distance 0.50 --int-target 210 --int-baseline 45

보험으로 같은 창에서 함께 돌릴 것:
  ros2 bag record /scan /ir_sensor/range -o dock-bench-bag

판정:
  python3 -c "from pathlib import Path; from rosy_core.docking.probe import \
read_rows, verdict; [print(v) for v in verdict(read_rows(Path('OUT')))]"
GUIDE
```

- [ ] **Step 2: Make it executable and check it refuses a bad band**

```bash
chmod +x deploy/robot/measure-dock-baseline.sh
bash deploy/robot/measure-dock-baseline.sh /tmp/x.csv bright; echo "exit=$?"
```

Expected: `알 수 없는 ambient: bright` and `exit=2`.

- [ ] **Step 3: Extend the DOCK_GO checklist**

In `docs/deployment/pi5-acceptance-checklist.md`, at the end of §7.6, append:

```markdown
### 7.6.1 감지기 후보 계측 (측정 리그)

- [ ] `/scan` 의 `intensities` 가 상수인가. 상수면 intensity 후보는 측정 없이
      탈락이고 아래 intensity 항목을 건너뛴다
- [ ] `measure-dock-baseline.sh` 를 세 주변광 구간(dark / indoor / direct-sun)
      각각에서 돌려 하나의 CSV 에 모았는가
- [ ] 도크 없는 표본이 구간마다 10개 이상 들어갔는가. 0개면 거짓 양성 기준이
      검사되지 않고 판정은 FAIL 로 나온다
- [ ] `verdict()` 출력을 그대로 기록했는가 — 통과·탈락과 metrics 전부
- [ ] 기하 후보의 **사용 가능 거리 구간 하단**(`envelope_low_m`)을 기록했는가.
      이 값이 그 도크 기종의 `docking_threshold_m` 을 정한다
- [ ] IR 의 응답 시작 거리를 주변광 구간별로 기록했는가
- [ ] 같은 세션의 `ros2 bag` 을 남겼는가 (환산이 틀렸을 때 물리 실험을 다시
      하지 않기 위한 보험)
```

- [ ] **Step 4: Update the docking AGENTS.md key-files table**

In `src/rosy_core/rosy_core/docking/AGENTS.md`, add two rows to the Key Files
table after the `agent.py` row:

```markdown
| `profile.py` | `DockProfile`, `fit()` — three asymmetric posts in a flat scan → `base_link` pose |
| `probe.py` | `ProbeRow` CSV schema + `verdict()` — picks the detector from measured rows |
```

And under Testing Requirements, add:

```bash
python3 -m pytest src/rosy_core/test/test_dock_profile.py src/rosy_core/test/test_dock_probe.py -v
```

- [ ] **Step 5: Sync the design doc's schema list**

The design doc lists the CSV fields but predates `dock_present`. In
`docs/plans/2026-09-07-dock-detector-measurement-rig-design.md`, in the
"3계층" section, change the `출처:` bullet to:

```markdown
- 출처: `lane`(sim/bench), `candidate`(geometry/intensity/ir),
  `dock_present`(도크가 앞에 있었는가 — 거짓 양성과 주변광 바닥을 이 칸이 가른다)
```

- [ ] **Step 6: Run everything and commit**

```bash
cd src/rosy_core && python -m pytest test/ -q
```

Expected: PASS, no regressions.

```bash
git add deploy/robot/measure-dock-baseline.sh \
        docs/deployment/pi5-acceptance-checklist.md \
        src/rosy_core/rosy_core/docking/AGENTS.md \
        docs/plans/2026-09-07-dock-detector-measurement-rig-design.md
git commit -m 'docs(dock): make the bench refuse a measurement that cannot be judged'
```

---

## What this plan deliberately leaves alone

- `services.py` keeps injecting `SimulatedDetector(script=[])`. Wiring a real
  detector is gated on a passing verdict, not on the code existing.
- `docking.supported` stays `false` in all four capability files.
- `manager.py` is untouched. If the geometric envelope falls short of
  `docking_threshold_m`, that is absorbed by per-type configuration.
- No `DockType.detector` plugin dispatch — the verdict has not chosen yet.
- No mechanical dimensions. The SDF is a measurement shape.
