"""rosy_core.docking.profile — 스캔에서 도크 기둥 배치를 찾아 상대 포즈를 낸다.

**횡방향은 방위각으로, 깊이만 거리로 잰다.** 방위각에는 거리 잡음이 없어서 이
추정기의 횡오차는 거리 잡음이 6배 변해도 거의 움직이지 않는다(0.70 → 0.57 mm).
그 성질이 V 면 대신 기둥을 고른 이유다 — V 는 잡음에 비례해서, 통과 여부가 아직
아무도 재지 않은 C1 잡음에 인질로 잡힌다.

**기둥 배치는 일부러 일직선이 아니다.** 가운데 기둥을 로봇 쪽(도크 프레임 −x)으로
20 mm 내밀었다. 세 기둥이 한 직선 위에 있으면 그 배치가 자기 축에 대한 거울에
불변이라 아무 세 점이 양손 어느 쪽으로든 맞을 수 있고, residual 은 "간격이 맞는
일직선" 이상을 보지 못한다. 값은 감으로 고르지 않고 0/10/20/30/40 mm 를 전부
쟀다(포즈 1,000회 × 거리 0.25–0.70 m·횡 ±60 mm·요 ±15°, 무작위 원통 세 개
120,000장):

| 내민 양 | 거짓 양성 | 요 RMS | 횡 RMS | 미획득 σ=3.5 mm | 미획득 σ=20 mm |
|---|---|---|---|---|---|
| 0 mm | 0.187% | 4.19° | 0.93 mm | 0/1000 | 0/1000 |
| 10 mm | 0.179% | 4.15° | 0.80 mm | 0/1000 | 0/1000 |
| **20 mm** | **0.177%** | **4.04°** | **0.71 mm** | **0/1000** | **0/1000** |
| 30 mm | 0.168% | 3.90° | 0.75 mm | 2/1000 | 0/1000 |
| 40 mm | 0.158% | 3.75° | 0.91 mm | 17/1000 | 8/1000 |

20 mm 을 고른 이유는 **획득률을 전혀 깎지 않는 가장 큰 값**이고 횡 RMS 가 가장
좋은 값이라서다. 더 내밀면 거짓 양성이 계속 줄지만 아주 천천히 줄고, 30 mm 부터
획득을 잃기 시작한다. 잃는 자리가 하필 요가 붙은 근거리(0.27–0.54 m, 요 9–15°)
인데, 가운데 기둥이 앞으로 나오면 요가 붙었을 때 그 기둥의 방위각이 한쪽 바깥
기둥으로 밀려 둘이 한 클러스터로 붙기 때문이다. 그 구간의 하단을 재는 것이 이
리그의 측정 목표 중 하나이므로, 거짓 양성 0.02%를 얻자고 측정 대상을 망가뜨리는
거래는 하지 않는다.

**이 변경은 거짓 양성을 0 으로 만들지 못한다. 그 사실을 숨기지 않는다.** 강체
3점 정합의 통과 조건은 결국 변 세 개가 공차 안에 드는 것이고 그 공차 부피는
모양을 바꿔도 거의 그대로다. 일직선을 깨서 없앤 것은 거울 중복(≈2배가 상한)이고
측정된 개선은 20 mm 에서 5%, 40 mm 에서도 16% 에 그친다. 설계의 **"거짓 양성 0"
기준은 이 피팅 하나로 도달하지 않는다** — 기둥을 넷으로 늘려 제약을 둘 더 얹거나,
게이트를 좁히거나(σ = 20 mm 의 진짜 도크가 13 mm 를 쓰므로 18 mm 아래로는 못
내린다), 다른 신호를 겹쳐야 한다. 리그의 판정이 그 결정을 받는다.

ROS 무의존 — 평평한 배열을 받고 `base_link` 기준 포즈를 돌려준다. 스캔 메시지를
보지 않으므로 host pytest 가 이 결정을 전부 본다(criterion C1).

설계: docs/plans/2026-09-07-dock-detector-measurement-rig-design.md
"""

from __future__ import annotations

import itertools
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
    #: 같은 순서의 기둥 전후 위치. 로봇은 도크의 **−x** 면으로 들어오므로
    #: "로봇 쪽으로 내민다"는 음수다. 전부 0(일직선)도 설정으로는 허용한다 —
    #: 못 돈다는 뜻이 아니라 거울 중복이 살아난다는 뜻이고, 그 차이는 측정으로
    #: 남겨야지 검증기로 숨길 것이 아니다. 기본값이 선택을 담는다(모듈 docstring
    #: 의 표). 이 20 mm 는 도크 기구 도면과 Gazebo SDF 에 들어가야 하는 값이다.
    post_forward_m: tuple[float, ...] = (0.0, -0.020, 0.0)
    #: 18 mm 은 재서 고른 값이다. 시뮬 잡음 σ = 20 mm 에서 정상 도크의 최악
    #: residual 이 400회 중 13.0 mm 였고, 간격이 어긋난 배치는 잡음 없이도
    #: 21.8 mm 였다. 게이트는 그 둘 사이에 있어야 한다 — 좁히면 진짜 도크를
    #: 거부하고, 넓히면 아무 기둥 세 개나 도크가 된다.
    max_residual_m: float = Field(default=0.018, gt=0.0)
    #: 거리 단차로 클러스터를 자르는 임계. 선언 잡음 σ = 20 mm 의 4배다.
    #: 처음 판은 이것을 30 mm 로 두었고 σ = 20 mm 에서 400회 중 398회를
    #: 놓쳤다 — 30 mm 가 잡음 안에 있었기 때문이다. 거리를 버리는 것이 답이
    #: 아니라 임계를 잡음에 맞춰 키우는 것이 답이었다. 기종별로 조정한다.
    max_range_step_m: float = Field(default=0.080, gt=0.0)
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
        if len(self.post_forward_m) != len(self.post_lateral_m):
            raise ValueError("post_forward_m must have one entry per post")
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

    def post_points(self) -> tuple[tuple[float, float], ...]:
        """(전후, 횡) 기둥 좌표, 횡 오름차순.

        정렬해서 돌려주는 이유: 대응이 방위각 순서로 성립하므로 모델도 같은
        순서여야 한다. 설정이 기둥을 아무 순서로 적어도 되게 하려면 정렬은
        여기서 한 번 하고, 짝(전후, 횡)이 함께 움직여야 한다.
        """
        return tuple((forward, lateral) for forward, lateral
                     in sorted(zip(self.post_forward_m, self.post_lateral_m),
                               key=lambda pair: pair[1]))


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
    #: 기둥 후보로 살아남은 클러스터 수. 배경이 있는 장면에서 `clusters` 는 벽
    #: 조각까지 세므로 둘이 갈라진다. 리그가 봐야 하는 것은 갈라진 쪽이다.
    candidates: int = 0

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


#: 각도 간극은 광선 간격의 몇 배부터 "다른 물체"인가.
#:
#: 1.5 는 후보 부분집합 선택이 들어오기 전까지 최대한 취약한 값이었다 — 광선
#: 하나가 빠지면 기둥이 둘로 갈라지고, "갈라진 개수가 3이 아니다"는 이유로
#: 스캔이 통째로 거부됐다. 지금은 갈라진 반쪽도 후보로 남고 부분집합이 답을
#: 찾으므로 0.5 m 에서는 1.01–4.0 어느 값이든 단일 결손 44가지를 전부 견딘다.
#: 그래서 이 상수가 실제로 정하는 것은 두 경계다. 둘 다 재서 확인했다:
#:
#: - **아래**: 기둥에 광선이 3개뿐인 먼 거리(1.10 m)에서 결손 하나가 그 기둥을
#:   1+1 로 쪼개면 양쪽이 `min_points_per_post` 밑으로 떨어져 후보가 둘이 된다.
#:   1.01 은 결손 9가지 중 3가지에서 그렇게 깨지고, 2.5 는 0/9 이다.
#: - **위**: 요가 붙으면 기둥들이 방위각에서 몰린다. 0.60 m·요 **+20°** 에서
#:   3.0 은 세 기둥을 한 클러스터로 붙여 버리고(후보 1개, 찾음=False), 2.5 는
#:   갈라 놓는다(후보 3개, 찾음=True). 이 지점이
#:   `test_a_yawed_dock_still_separates_into_three_posts` 가 도는 지점이다.
#:   예전 판은 천장을 0.70 m·요 15° 로 적었으나 **재보면 거기서는 3.0 도
#:   멀쩡히 셋으로 갈라진다**(후보 3개, 찾음=True). 상수 옆의 숫자가 재현되지
#:   않으면 상수의 근거가 없어지므로, 실제로 깨지는 지점만 적는다.
#:
#: 2.5 는 그 두 경계 사이다. 설계 문서가 입사각에 따른 신호 소실을 "모델하지
#: 않는 것"으로 적어 두었으므로, 아래쪽(결손) 여유를 넉넉히 두는 쪽을 골랐다.
_GAP_FACTOR = 2.5


def _cluster(points: list[tuple[float, float]], angle_increment: float,
             profile: DockProfile) -> list[list[tuple[float, float]]]:
    """각도 간극 **또는** 거리 단차로 자른다.

    각도 간극만으로 자르는 판은 **도크가 허공에 서 있다고 가정한 것**이었다.
    기둥 사이로 지나간 광선이 아무것도 맞히지 않는다는 전제는 `max_range_m`
    안에 배경이 없을 때만 성립한다. 실제 방에서는 벽이 모든 방위각을 채우므로
    간극이 어디에도 없고 장면 전체가 클러스터 하나가 된다 — 0.60 m 와 1.00 m
    벽에서 실행으로 확인했다(찾음=False, 클러스터=1). 그 상태로 리그를 돌리면
    획득률이 0에 가깝게 나오는데, 그것은 도크 형상에 대한 판정이 아니라
    클러스터링 규칙에 대한 판정이다.

    그래서 거리 단차를 **보조** 기준으로 넣는다. 주 기준은 여전히 각도 간극이다
    — 거기에는 거리 잡음이 없다. 단차 임계는 잡음의 4배(σ = 20 mm 에서 80 mm)로,
    처음 판이 30 mm 로 쓰고 400회 중 398회를 놓친 실패를 되풀이하지 않을 만큼 크다.

    단차를 **직전 점이 아니라 지금 클러스터의 거리 평균**과 비교한다. 직전
    점과 비교하면 차이에 실리는 잡음이 σ√2 라서 80 mm 는 2.8σ 밖에 안 되고,
    기둥 하나에서 5.5%(400회 중 22회)가 잡음만으로 갈라졌다. 갈라진 반쪽은
    방위각 평균이 치우쳐서 그 회차의 포즈를 망친다 — 실제로 그것이 요 RMS 의
    지배 항이었다(2.8° → 4.2°). 평균과 비교하면 잡음이 σ 라서 80 mm 가 진짜
    4σ 가 되고, 같은 임계가 배경은 그대로 자르면서 기둥은 자르지 않는다.

    **이것은 도크 기구에 거는 제약이다.** 기둥은 스캔 높이(바닥 95 mm)에서 자기
    뒤에 있는 것보다 `max_range_step_m`(기본 80 mm)보다 더 앞에 서 있어야 한다.
    벽에 딱 붙인 도크는 이 규칙으로 분리되지 않는다. 도크가 아직 만들어지지
    않았으므로 이것은 판정 결과가 아니라 기구 설계에 들어가는 입력이다.
    """
    gap = _GAP_FACTOR * abs(angle_increment)
    step = profile.max_range_step_m
    clusters: list[list[tuple[float, float]]] = []
    current = [points[0]]
    total = points[0][1]
    for previous, point in zip(points, points[1:]):
        mean_range = total / len(current)
        if point[0] - previous[0] > gap or abs(point[1] - mean_range) > step:
            clusters.append(current)
            current = [point]
            total = point[1]
        else:
            current.append(point)
            total += point[1]
    clusters.append(current)
    return clusters


#: 반지름 r 기둥이 거리 d 에서 차지하는 방위각 폭은 2·asin(r/d) 이고 벽 조각은
#: 그보다 한 자릿수 넓다. 여유 1.5배는 혼합 픽셀이 진짜 기둥의 양 끝을 광선
#: 한두 개 넓히는 경우를 위한 것이다 — 설계 문서가 혼합 픽셀을 "모델하지 않는
#: 것"으로 적어 두었다. 넓은 쪽만 막는 상한이다. 좁은 쪽은 `min_points_per_post`.
_WIDTH_SLACK = 1.5

#: 후보가 이보다 많으면 조합을 뒤지지 않고 값으로 거부한다. 12개면
#: C(12, 3) = 220 가지 — 10 Hz 틱 안에서 무해하다. 상한이 필요한 이유는 비용이
#: 후보 수의 세제곱으로 늘기 때문이고, 12 를 고른 이유는 `max_range_m` 안 전방
#: 창에 기둥 굵기의 물체가 12개 넘게 서 있는 장면은 도크 장면이 아니어서 더
#: 뒤져도 답이 없기 때문이다. 거부는 예외가 아니라 사유가 붙은 값이다.
_MAX_POST_CANDIDATES = 12


def _looks_like_a_post(cluster: list[tuple[float, float]],
                       profile: DockProfile,
                       angle_increment: float) -> bool:
    """방위각 폭으로 기둥 후보를 고른다.

    거리 단차로 벽을 자르고 나면 클러스터가 셋보다 많아진다. 어느 셋이 기둥인지
    조합으로만 찾으면 비싸고, 폭은 싸고 원리가 있다 — 기둥은 2·asin(r/d) 만큼만
    차지하고 벽 조각은 그보다 훨씬 넓다.
    """
    span = cluster[-1][0] - cluster[0][0]
    mean_range = sum(item[1] for item in cluster) / len(cluster)
    half_width = math.asin(min(1.0, profile.post_radius_m / mean_range))
    # 광선 간격 두 개는 이산화 여유다. 먼 기둥은 폭이 광선 간격과 비슷해져서,
    # 여유가 없으면 진짜 기둥이 자기 폭 때문에 떨어진다.
    return span <= _WIDTH_SLACK * 2.0 * half_width + 2.0 * abs(angle_increment)


#: 반지름 r 기둥의 보이는 앞면에서 거리는 정면 d−r 부터 가장자리 d 까지 변한다.
#: 등간격 광선은 앞면을 **현(chord) 위에서 등간격으로** 훑으므로(횡 오프셋 u 가
#: 균일) 평균은 d − (π/4)r 이고, 그래서 평균에 이 값을 되돌려 더한다. 호 길이로
#: 균일하게 훑었다면 평균은 d − (2/π)r 이다 — 값이 아니라 **어느 평균인지**가 이
#: 상수의 정체이고, 예전 이름은 그것을 정확히 반대로 적고 있었다.
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


def _procrustes(model: Sequence[tuple[float, float]],
                observed: Sequence[tuple[float, float]]
                ) -> tuple[float, float, float, float]:
    """관측 중심들을 알려진 배치에 회전+평행이동으로 맞춘다.

    돌려주는 것은 (yaw, tx, ty, rms residual). 도크 원점은 모델의 (0, 0) 이므로
    평행이동이 곧 도크 원점의 센서 프레임 좌표다 — 관측 중심의 평균이 아니다.

    **길이 불일치는 값이 아니라 예외다.** `zip` 은 짧은 쪽에서 조용히 멈추므로
    관측이 모델보다 길면 앞쪽 몇 개만 채점하고 "잔차가 작다"고 보고한다. 그것은
    거짓 양성을 만드는 종류의 침묵이다. `fit` 은 언제나 같은 개수를 넘기므로 이
    예외는 스캔 데이터로 도달할 수 없고, 도달했다면 호출자 버그다.
    """
    count = len(model)
    if count == 0 or len(observed) != count:
        raise ValueError(
            "procrustes needs equal, non-empty point sets; got "
            f"{count} model and {len(observed)} observed")

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
    model = profile.post_points()
    wanted = len(model)
    points = _forward_points(ranges, angle_min, angle_increment, profile)
    if len(points) < profile.min_points_per_post * wanted:
        return ProfileFit(reason="too few returns in the forward window",
                          points=len(points))

    clusters = _cluster(points, angle_increment, profile)
    candidates = [cluster for cluster in clusters
                  if len(cluster) >= profile.min_points_per_post
                  and _looks_like_a_post(cluster, profile, angle_increment)]

    # **개수가 틀렸다고 거부하지 않는다.** 거리 단차로 배경을 자르고 나면 셋보다
    # 많은 것이 정상이다. 예전 판의 `len(clusters) != wanted` 는 배경이 있는
    # 모든 장면을 거부했고, 그것이 리그가 낼 뻔한 잘못된 판정의 정체였다.
    if len(candidates) < wanted:
        return ProfileFit(
            reason=f"only {len(candidates)} post-shaped clusters, need {wanted}",
            points=len(points), clusters=len(clusters),
            candidates=len(candidates))
    if len(candidates) > _MAX_POST_CANDIDATES:
        return ProfileFit(
            reason=f"{len(candidates)} post-shaped clusters over the "
                   f"{_MAX_POST_CANDIDATES} candidate cap",
            points=len(points), clusters=len(clusters),
            candidates=len(candidates))

    centres = [_post_centre(cluster, profile.post_radius_m)
               for cluster in candidates]
    # 후보는 방위각 오름차순이고 `combinations` 가 그 순서를 지킨다 — 대응이
    # 방위각 순서로 성립하므로 부분집합마다 다시 정렬할 필요가 없다.
    best: Optional[tuple[float, float, float, float]] = None
    for chosen in itertools.combinations(centres, wanted):
        attempt = _procrustes(model, chosen)
        if best is None or attempt[3] < best[3]:
            best = attempt
    yaw, tx, ty, residual = best

    if residual > profile.max_residual_m:
        return ProfileFit(
            reason=f"residual {residual:.4f} m over {profile.max_residual_m:.4f} m",
            residual_m=residual, points=len(points), clusters=len(clusters),
            candidates=len(candidates))

    bx, by, byaw = _to_base_link(tx, ty, yaw, sensor)
    # `confidence` 는 residual 의 단조 감소 함수일 뿐이다. **우도가 아니고,
    # 보정되지 않았고, 검출기 사이에 비교할 수도 없다.** σ = 20 mm 의 진짜
    # 도크가 0.28–0.98 을 받는 동안 무작위 원통 세 개의 거짓 양성이 0.02–0.48 을
    # 받았으므로, 이 값에 임계를 걸어 둘을 가를 수 없다 — 가르는 것은
    # `max_residual_m` 이다. `SimulatedDetector` 는 같은 `DockObservation`
    # 필드에 1.0 을 박아 넣으므로 검출기 사이에 비교하면 틀린다. 오늘 이 값을
    # 소비하는 코드는 없고, 리그의 CSV 기록 항목으로만 둔다.
    return ProfileFit(
        observation=DockObservation(
            x=bx, y=by, yaw=byaw,
            confidence=max(0.0, 1.0 - residual / profile.max_residual_m),
            at=now),
        residual_m=residual, points=len(points), clusters=len(clusters),
        candidates=len(candidates))
