"""rosy_core.docking.profile — 스캔에서 도크 기둥 배치를 찾아 상대 포즈를 낸다.

**횡방향은 방위각으로, 깊이만 거리로 잰다.** 방위각에는 거리 잡음이 없어서 이
추정기의 횡오차는 거리 잡음이 6배 변해도 거의 움직이지 않는다(0.87 → 0.60 mm).
그 성질이 V 면 대신 기둥을 고른 이유다 — V 는 잡음에 비례해서, 통과 여부가 아직
아무도 재지 않은 C1 잡음에 인질로 잡힌다.

ROS 무의존 — 평평한 배열을 받고 `base_link` 기준 포즈를 돌려준다. 스캔 메시지를
보지 않으므로 host pytest 가 이 결정을 전부 본다(criterion C1).

설계: docs/plans/2026-09-07-dock-detector-measurement-rig-design.md
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

from pydantic import BaseModel, Field, field_validator, model_validator

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

    @model_validator(mode="after")
    def _layout_must_be_resolvable(self) -> "DockProfile":
        """돌 수 없는 배치는 설정 시각에 거부한다 — 이 검증기의 일이다."""
        ascending = sorted(self.post_lateral_m)
        floor = 2.0 * self.post_radius_m
        for previous, lateral in zip(ascending, ascending[1:]):
            if lateral - previous <= floor:
                # 반지름 두 개보다 가까우면 두 기둥이 서로 붙어 있어서 스캔에서
                # 절대 따로 떨어지지 않는다. 같은 값이면 물리적으로 겹친다.
                raise ValueError(
                    "adjacent posts must be more than 2 * post_radius_m apart; "
                    f"{previous} and {lateral} are not")
        return self


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


#: 반지름 r 원통의 보이는 앞면에서 거리는 중심에서 d−r(정면)부터 d(가장자리)까지
#: 변한다. 등간격 광선은 그 앞면을 **현(chord) 위에서 등간격으로** 훑으므로(횡
#: 오프셋 u 가 균일) 평균은 d − (π/4)r 이고, 그래서 평균에 이 값을 되돌려 더한다.
#: 호 길이로 균일하게 훑었다면 평균은 d − (2/π)r 이다 — 값이 아니라 **어느
#: 평균인지**가 이 상수의 정체이고, 예전 이름은 그것을 정확히 반대로 적고 있었다.
_CHORD_MEAN_BIAS = math.pi / 4.0


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
    distance = mean_range + _CHORD_MEAN_BIAS * radius
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
    # `confidence` 는 residual 의 단조 감소 함수일 뿐이다. **우도가 아니고,
    # 보정되지 않았고, 검출기 사이에 비교할 수도 없다.** σ = 20 mm 의 진짜
    # 도크가 0.28–0.98 을 받는 동안 무작위 원통 세 개의 거짓 양성이 0.02–0.48 을
    # 받으므로, 이 값에 임계를 걸어 둘을 가를 수 없다 — 가르는 것은
    # `max_residual_m` 이다. `SimulatedDetector` 는 같은 `DockObservation`
    # 필드에 1.0 을 박아 넣으므로 검출기 사이에 비교하면 틀린다. 오늘 이 값을
    # 소비하는 코드는 없고, 리그의 CSV 기록 항목으로만 둔다.
    return ProfileFit(
        observation=DockObservation(
            x=bx, y=by, yaw=byaw,
            confidence=max(0.0, 1.0 - residual / profile.max_residual_m),
            at=now),
        residual_m=residual, points=len(points), clusters=len(clusters))
