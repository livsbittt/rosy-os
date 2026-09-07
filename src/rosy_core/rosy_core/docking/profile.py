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
