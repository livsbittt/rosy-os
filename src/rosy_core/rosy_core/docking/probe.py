"""rosy_core.docking.probe — 측정 기록과, 감지 방식을 고르는 판정.

**두 갈래가 같은 표를 쓰고 같은 판정을 통과한다.** Gazebo 스윕과 실기 벤치가
각자 CSV 를 쓰면 판정이 셋으로 갈라지고, 그 순간 후보들이 비교 불가능해진다.
해당 없는 칸은 빈칸으로 남고, 빈칸은 0 이 아니다.

**같은 표를 쓰지만 판정은 갈래별로 낸다.** 자로 잰 벤치 정답과 시뮬의 정확한
정답을 한 RMS 에 섞으면 자의 오차가 시뮬 숫자를 오염시키고, sim 500 줄이
bench 50 줄을 희석해서 어느 갈래가 떨어졌는지 알 수 없게 된다. 설계의 표본
하한도 갈래별로 적혀 있어서, 갈래를 나누지 않으면 검사 자체가 불가능하다.

판정 기준의 숫자는 측정 *전에* 정해졌다. 측정 후에 기준을 정하면 원하는 답이
나온다. 그래서 상수가 이 파일 맨 위에 있고 설계 문서와 같은 값이다.

**NaN 은 모든 `>` 비교를 조용히 만족시킨다.** 그래서 이 파일의 모든 지표는
비교 전에 `math.isfinite` 를 통과해야 하고, 통과하지 못하면 그 자체가 사유가
된다 — 가드 없는 지표는 없는 지표보다 나쁘다. 없는 지표는 사유를 남기지만,
NaN 인 지표는 통과 도장을 찍는다.

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
#: 사용 가능 구간의 하단을 걸어 내려갈 때 허용하는 격자 간격. 걷는 방향은
#: 스테이징에서 아래쪽뿐이고, `dock_sweep.py --distances` 의 스테이징 이하
#: 구간에서 가장 넓은 칸이 0.08 m 다(0.13·0.15 칸은 스테이징 *위* 에만 있어
#: 걸어 지나가지 않는다). 이보다 성긴 격자는 자기 간격보다 정확하게 하단을
#: 짚을 수 없고, 이 숫자가 그대로 `DockType.docking_threshold_m` 로 들어간다 —
#: 성긴 격자로 추측하는 대신 거부한다.
ENVELOPE_STEP_MAX_M = 0.10
#: intensity 겹침을 보는 거리 칸. 봉투 걸음의 상수와 **달라야 한다** —
#: 예전에는 한 상수가 두 일을 했고, 격자 구멍을 메우려 칸을 넓히면 intensity
#: 판정이 조용히 엄해졌다(칸이 넓어지면 min(target) − max(baseline) 여유가
#: 줄어든다). 0.05 m 는 벤치에서 손으로 옮기는 간격이다.
INTENSITY_BIN_M = 0.05
#: IR 좌우 편차를 보는 횡 밴드(센서 베이스라인 ±20 mm).
IR_BAND_M = 0.020
#: 그 편차를 재는 접점 밴드의 거리 상한. 밴드를 횡으로만 자르면 온셋 측정용
#: (truth_y = 0) 줄이 거리마다 함께 들어와 편차 0 으로 분모를 채운다 — 같은
#: 팔이 요구하는 두 측정이 서로를 무너뜨렸다. `IR_ONSET_MIN_M` 과 값이 같은
#: 것은 우연이 아니다: 편차가 일해야 하는 구간이 곧 접점 판정 구간이다.
IR_CONTACT_MAX_M = 0.05
#: 움직인 인접쌍 중 부호가 뒤집히지 않아야 하는 비율. 동률은 분모에서 뺀다 —
#: 정수 카운트로 보고하는 센서는 중앙 근처에서 반드시 동률이 나오고, 그것을
#: 방향 실패로 청구하면 뒤집힘이 하나도 없는 센서가 탈락한다.
IR_NO_INVERSION_MIN = 0.80
#: 응답 시작 거리가 이보다 짧으면 접점 판정에 쓸 수 없다
#: (`DockType.docking_threshold_m` 기본값과 같은 숫자).
IR_ONSET_MIN_M = 0.05
#: 주변광 바닥 위로 이만큼(비율) 은 넘어야 "응답했다"로 센다. 바닥은 몇 줄의
#: 도크 없는 표본에 대한 max 라서 실제 천장은 그보다 위에 있고, 온셋은 *큰*
#: 쪽이 통과하는 지표다 — 여유가 없으면 잡음이 통과를 사 온다.
IR_FLOOR_MARGIN = 0.05

#: 설계가 못 박은 도크 없는 스캔 하한(§판정 "거짓 양성 0"): sim ≥ 500장,
#: 벤치 ≥ 50장. 표본 하나로 "거짓 양성 0" 을 인증할 수 있으면 그 기준은
#: 기준이 아니다.
MIN_ABSENT = {"sim": 500, "bench": 50}
#: 스테이징 띠 표본 하한. 설계가 직접 적은 숫자는 아니지만 설계에서 나온다.
#: sim: 격자(거리 0.68/0.70/0.72 × 횡 7 × 요 5)가 띠 안에 105 표본을 넣는다 —
#: 100 은 "그 격자를 실제로 돌렸는가" 를 묻는 하한이다. bench: 획득률 95%
#: 기준은 1/(1 − 0.95) = 20 표본부터 의미가 생긴다(그 아래에서는 한 번만
#: 놓쳐도 자동 탈락이라 비율을 재는 것이 아니다).
MIN_STAGING = {"sim": 100, "bench": 20}

#: 갈래는 이 둘뿐이다. 표본 하한이 갈래별로 선언되므로 모르는 갈래는 판정할
#: 수 없다 — BOM 하나로 `lane` 이 빈칸이 되는 사고를 여기서 잡는다.
LANES = ("sim", "bench")


FIELDS = ("lane", "candidate", "dock_present", "truth_x", "truth_y",
          "truth_yaw", "ambient", "fit_x", "fit_y", "fit_yaw", "residual",
          "points", "confidence", "int_target", "int_baseline",
          "ir_l", "ir_mid", "ir_r")


class ProbeFormatError(ValueError):
    """CSV 칸 하나를 읽을 수 없다. 파일·줄·칸을 메시지에 담는다.

    판정의 실패는 값으로 돌려주지만(`ProbeVerdict.reasons`), 파싱 실패는
    돌려줄 줄이 없다. `ValueError` 를 상속하는 이유는 예전 판이 맨 `ValueError`
    를 던졌고 부르는 쪽이 그것을 잡고 있을 수 있어서다. 고친 것은 예외의
    종류가 아니라 **어느 파일 어느 줄 어느 칸인지 말하지 않던 것**이다.
    """


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
_TEXT_FIELDS = frozenset({"lane", "candidate", "ambient"})

#: 양쪽을 다 화이트리스트로 둔다. 예전 판은 `text not in ("0","false","False")`
#: 였고, 그래서 `FALSE`·`no`·`off`·`0.0` 이 전부 "도크 있었다"로 읽혔다 —
#: 거짓 양성 집계가 조용히 뒤집히는 자리이고, 손으로 쓴 CSV 는 예상된 입력이다.
_TRUE_TEXT = frozenset({"1", "true", "yes"})
_FALSE_TEXT = frozenset({"0", "false", "no"})


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


def _decode_dock_present(text: str) -> bool:
    if text == "":
        # 빈칸은 dataclass 기본값(True)과 같게 읽는다. 손으로 쓴 CSV 에서
        # 칸이 비었다고 "도크가 없었다"로 뒤집히면 거짓 양성 집계가 조용히
        # 부풀어 통과할 후보를 떨어뜨린다.
        return True
    lowered = text.lower()
    if lowered in _TRUE_TEXT:
        return True
    if lowered in _FALSE_TEXT:
        return False
    raise ProbeFormatError(
        f"{text!r} is neither true (1/true/yes) nor false (0/false/no)")


def _decode(record: dict[str, str]) -> ProbeRow:
    kwargs: dict[str, Any] = {}
    for field in fields(ProbeRow):
        text = (record.get(field.name) or "").strip()
        if field.name == "dock_present":
            kwargs[field.name] = _decode_dock_present(text)
        elif field.name in _TEXT_FIELDS:
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


def _blame(record: dict[str, str], exc: ValueError) -> str:
    """어느 칸이 터졌는지 되짚는다. 못 짚으면 원래 메시지를 그대로 쓴다."""
    for field in fields(ProbeRow):
        text = (record.get(field.name) or "").strip()
        try:
            if field.name == "dock_present":
                _decode_dock_present(text)
            elif field.name in _TEXT_FIELDS or text == "":
                continue
            elif field.name in _INT_FIELDS:
                int(float(text))
            elif field.name in _FLOAT_FIELDS:
                float(text)
        except ValueError:
            return f"column {field.name}: {text!r}"
    return str(exc)


def read_rows(path: Path) -> list[ProbeRow]:
    """CSV 를 읽는다. 못 읽는 칸은 파일·줄·칸을 대며 거부한다.

    `utf-8-sig` 인 이유: Excel 이 BOM 을 쓴다. 맨 `utf-8` 로 열면 첫 헤더
    이름이 `﻿lane` 이 되어 `lane` 이 조용히 빈칸이 되고, 그러면 갈래별
    판정이 통째로 "모르는 갈래" 로 무너진다.
    """
    target = Path(path)
    with target.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[ProbeRow] = []
        for record in reader:
            try:
                rows.append(_decode(record))
            except ValueError as exc:
                # 손으로 고친 CSV 는 예상된 입력이다. 어느 칸인지 말하지 않는
                # 예외는 수백 줄짜리 측정 파일 앞에서 아무 쓸모가 없다.
                raise ProbeFormatError(
                    f"{target}:{reader.line_num} {_blame(record, exc)}"
                ) from exc
        return rows


@dataclass(frozen=True)
class ProbeVerdict:
    """후보 하나 × 갈래 하나에 대한 판정. `reasons` 가 비면 통과다."""

    candidate: str
    lane: str
    passed: bool
    reasons: tuple[str, ...]
    metrics: dict[str, float]


def verdict(rows: Iterable[ProbeRow],
            lane: Optional[str] = None) -> tuple[ProbeVerdict, ...]:
    """(후보, 갈래) 쌍마다 판정을 낸다. 순서는 후보 이름, 그 다음 갈래 순이다.

    `lane` 을 주면 그 갈래만 본다. 갈래를 섞지 않는 이유는 모듈 docstring 에
    있다 — 자로 잰 정답과 시뮬 정답은 같은 RMS 에 들어갈 수 없다.

    빈 표는 빈 결과가 아니라 **실패**를 돌려준다. `all(v.passed for v in
    verdict(rows))` 가 자연스러운 사용법이고 빈 튜플에 대한 `all()` 은 True 라,
    아무것도 측정하지 않은 스윕이 그 모양으로 통과 도장을 받았다.
    """
    collected = [row for row in rows if lane is None or row.lane == lane]
    if not collected:
        where = "" if lane is None else f" for lane {lane!r}"
        return (ProbeVerdict("", lane or "", False,
                             (f"the table has no rows{where} — nothing was "
                              f"measured",), {}),)

    arms = {"geometry": _verdict_geometry,
            "intensity": _verdict_intensity,
            "ir": _verdict_ir}
    out = []
    for name, group in sorted({(row.candidate, row.lane) for row in collected}):
        subset = [row for row in collected
                  if row.candidate == name and row.lane == group]
        arm = arms.get(name)
        if arm is None:
            out.append(ProbeVerdict(name, group, False,
                                    ("unknown candidate",), {}))
        elif group not in LANES:
            out.append(ProbeVerdict(
                name, group, False,
                (f"unknown lane {group!r}, so the per-lane sample floors "
                 f"cannot be applied",), {}))
        else:
            out.append(arm(subset, group))
    return tuple(out)


def _rate(rows: Sequence[ProbeRow]) -> float:
    """포즈를 낸 표본의 비율.

    `is not None` 만으로는 부족하다. NaN 을 낸 피팅은 포즈를 낸 것이 아닌데,
    예전 판은 그것을 획득으로 세었고, 그래서 전 구간이 NaN 인 스윕이 획득률
    100% 로 보고되고 통과했다.
    """
    if not rows:
        return 0.0
    acquired = sum(1 for row in rows
                   if row.fit_x is not None and row.fit_y is not None
                   and math.isfinite(row.fit_x) and math.isfinite(row.fit_y))
    return acquired / len(rows)


def _envelope_low(rows: Sequence[ProbeRow]) -> float:
    """획득률이 기준 위로 유지되는 구간의 하단. 재지 못했으면 NaN.

    하단을 가정하지 않고 재는 이유: 접점 직전 수 cm 에서 기둥은 시야를 벗어난다.
    그 하단이 `docking_threshold_m` 에 못 미치면 기종 설정으로 흡수한다.

    **스테이징 띠에 닻을 내리고 아래로 걷는다.** 예전 판은 고정폭 칸으로 나눈
    뒤 위에서 아래로 훑다가 첫 구멍에서 멈췄고, 설계의 격자
    (0.30 → 0.40 → 0.50 → 0.60)가 칸에 구멍을 내기 때문에 사실상 구간의
    **상단**을 돌려줬다 — 0.25–0.85 m 에서 획득하는 검출기가 0.85 를 하단으로
    보고했다. 그 숫자가 로봇 설정으로 들어간다.

    칸을 아예 쓰지 않는 이유: 칸폭을 격자 구멍보다 넓히면 서로 다른 거리가 한
    칸에 섞여 하단이 격자 해상도보다 거칠어진다. 대신 측정된 거리 그 자체를
    걸어 내려가고, 격자가 `ENVELOPE_STEP_MAX_M` 보다 성기면 추측하지 않는다.
    """
    measured: dict[float, list[ProbeRow]] = {}
    for row in rows:
        if math.isfinite(row.truth_x):
            measured.setdefault(round(row.truth_x, 4), []).append(row)
    if not measured:
        return math.nan

    steps = sorted(measured)
    anchored = [step for step in steps
                if STAGING_BAND_M[0] <= step <= STAGING_BAND_M[1]
                and _rate(measured[step]) >= ACQUIRE_RATE_MIN]
    if not anchored:
        # 스테이징에서 못 잡았다 — 구간의 하단이랄 것이 없다.
        return math.nan

    low = min(anchored)
    while True:
        below = [step for step in steps if step < low]
        if not below:
            # 격자가 검출기보다 먼저 끝났다. 가장 가까운 표본에서도 잡혔다면
            # 하단은 그 아래 어딘가이고, 이 스윕은 그것을 재지 못한 것이다.
            return math.nan
        nxt = max(below)
        # 격자 간격은 0.1 처럼 정확히 표현되지 않는 값이라 `round` 없이
        # 비교하면 0.40 − 0.30 = 0.10000000000000003 이 상한을 넘는다.
        if round(low - nxt, 6) > ENVELOPE_STEP_MAX_M:
            # 그 아래는 이 격자가 답할 수 없다. 아는 하단을 낸다 — 임계는
            # 낮게 잡는 쪽이 아니라 높게 잡는 쪽이 안전하다.
            return low
        if _rate(measured[nxt]) < ACQUIRE_RATE_MIN:
            return low
        low = nxt


def _verdict_geometry(rows: Sequence[ProbeRow], lane: str) -> ProbeVerdict:
    """기하 후보.

    지표마다 `isfinite` 분기가 붙어 있는 것은 방어적 습관이 아니다. NaN 은
    모든 `>` 비교를 조용히 만족시켜서, 가드 없는 지표 하나가 판정 전체에
    통과 도장을 찍는다(모듈 docstring 참조).
    """
    present = [row for row in rows if row.dock_present]
    absent = [row for row in rows if not row.dock_present]
    reasons: list[str] = []
    metrics: dict[str, float] = {}

    staging = [row for row in present
               if math.isfinite(row.truth_x)
               and STAGING_BAND_M[0] <= row.truth_x <= STAGING_BAND_M[1]]
    rate = _rate(staging)
    metrics["acquire_rate"] = rate
    metrics["staging_samples"] = float(len(staging))
    if not staging:
        reasons.append("no samples inside the staging band")
    else:
        if len(staging) < MIN_STAGING[lane]:
            reasons.append(
                f"{len(staging)} staging samples, under the {lane} floor of "
                f"{MIN_STAGING[lane]}")
        if not math.isfinite(rate):
            reasons.append("the acquisition rate is not a number")
        elif rate < ACQUIRE_RATE_MIN:
            reasons.append(f"acquisition {rate:.1%} below {ACQUIRE_RATE_MIN:.0%}")

    gated = [row for row in present
             if row.fit_y is not None and math.isfinite(row.fit_y)
             and math.isfinite(row.truth_y) and math.isfinite(row.truth_x)
             and row.truth_x <= GATE_RANGE_MAX_M]
    if not gated:
        metrics["lateral_rms_m"] = math.inf
        reasons.append("no fits inside the gate window")
    else:
        rms = math.sqrt(sum((row.fit_y - row.truth_y) ** 2
                            for row in gated) / len(gated))
        metrics["lateral_rms_m"] = rms
        if not math.isfinite(rms):
            reasons.append("the lateral RMS is not a number")
        elif rms > LATERAL_RMS_MAX_M:
            reasons.append(
                f"lateral RMS {rms * 1000:.1f} mm over "
                f"{LATERAL_RMS_MAX_M * 1000:.0f} mm")

    # 도크 없는 줄이 포즈를 냈다면 그 포즈가 NaN 이든 아니든 거짓 양성이다.
    # `_rate` 와 비대칭인 것은 의도다 — 두 지표 모두 실패하는 쪽으로 기운다.
    hits = sum(1 for row in absent if row.fit_x is not None)
    metrics["false_positives"] = float(hits)
    metrics["absent_samples"] = float(len(absent))
    if not absent:
        reasons.append("no dock-absent samples, so false positives are untested")
    else:
        if len(absent) < MIN_ABSENT[lane]:
            reasons.append(
                f"{len(absent)} dock-absent samples, under the {lane} floor of "
                f"{MIN_ABSENT[lane]}")
        if hits:
            reasons.append(f"{hits} false positive(s)")

    low = _envelope_low(present)
    metrics["envelope_low_m"] = low
    if not math.isfinite(low):
        # 하단을 재는 것이 이 리그의 측정 목표 중 하나다. 재지 못한 스윕은
        # 통과가 아니다 — 예전 판은 `nan > 기준` 이 False 라는 이유만으로
        # 사유 한 줄 없이 통과했다.
        reasons.append(
            "the usable envelope lower bound was not measured: the staging "
            "band was not acquired, or the grid ran out before the fit did")
    return ProbeVerdict("geometry", lane, not reasons, tuple(reasons), metrics)


def _verdict_intensity(rows: Sequence[ProbeRow], lane: str) -> ProbeVerdict:
    """역반사와 무광이 모든 거리에서 갈라지는가.

    겹치면 탈락이다. 부분적으로만 갈라지는 intensity 로는 임계를 하나 고를 수
    없고, 거리에 따라 임계를 바꾸는 것은 감지기가 아니라 추측이다.

    `dock_present` 를 요구하는 이유: 도크 없이 찍은 줄에 반사값이 실려 있으면
    예전 판은 그것을 도크가 있었던 것처럼 칸에 넣었고, 빈 방 표본 하나가
    갈라짐 판정을 뒤집었다.
    """
    usable = [row for row in rows
              if row.dock_present
              and row.int_target is not None and row.int_baseline is not None
              and math.isfinite(row.int_target)
              and math.isfinite(row.int_baseline)
              and math.isfinite(row.truth_x)]
    if not usable:
        return ProbeVerdict("intensity", lane, False,
                            ("no dock-present rows carry both a target and a "
                             "baseline",), {})

    binned: dict[int, list[ProbeRow]] = {}
    for row in usable:
        binned.setdefault(round(row.truth_x / INTENSITY_BIN_M), []).append(row)

    reasons: list[str] = []
    worst = math.inf
    for key in sorted(binned):
        items = binned[key]
        margin = (min(row.int_target for row in items)
                  - max(row.int_baseline for row in items))
        worst = min(worst, margin)
        if not math.isfinite(margin):
            reasons.append(
                f"the margin at {key * INTENSITY_BIN_M:.2f} m is not a number")
        elif margin <= 0.0:
            reasons.append(
                f"retro and matte overlap at {key * INTENSITY_BIN_M:.2f} m "
                f"(margin {margin:.1f})")
    return ProbeVerdict("intensity", lane, not reasons, tuple(reasons),
                        {"worst_margin": worst})


def _verdict_ir(rows: Sequence[ProbeRow], lane: str) -> ProbeVerdict:
    """`ir_l - ir_r` 이 접점 밴드에서 좌우를 가르는가, 그리고 언제부터 응답하는가.

    주변광 구간마다 따로 본다. 판정을 가르는 것은 가장 밝은 구간이다 — 밝은
    곳에서 무너지는 감지기는 창가에 놓인 도크에서 쓸 수 없다.

    **동률은 방향 실패가 아니다.** 예전 판은 엄격한 `>` 로 순서 맞는 쌍을
    셌고, 그래서 정수 카운트로 보고하는 센서(중앙 근처에서 반드시 동률이
    나온다)가 뒤집힘 0 개인데도 36% 로 떨어졌다. 지금은 움직인 쌍만 분모에
    넣고 뒤집힘만 센다.

    **밴드는 횡과 거리 둘 다로 자른다.** 예전 판은 `abs(truth_y)` 만 봤고,
    같은 팔이 요구하는 온셋 측정(truth_y = 0, 거리 여러 개)이 전부 편차 0 으로
    밴드에 들어와 분모를 채웠다 — 거리를 다섯 개만 특성화해도 통과하던 센서가
    떨어졌다. 두 측정이 서로를 무너뜨렸고 출력만 봐서는 알 수 없었다.
    """
    reasons: list[str] = []
    metrics: dict[str, float] = {}
    bands = sorted({row.ambient for row in rows if row.ambient})
    if not bands:
        return ProbeVerdict("ir", lane, False, ("no ambient band recorded",), {})

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
        # 바닥이 0 인 채널에서도 최소 1 카운트는 넘어야 응답으로 센다.
        threshold = floor + max(1.0, floor * IR_FLOOR_MARGIN)
        metrics[f"floor_{band}"] = float(floor)

        skewed = sorted(
            (row for row in in_band
             if row.dock_present and row.ir_l is not None and row.ir_r is not None
             and math.isfinite(row.truth_y) and abs(row.truth_y) <= IR_BAND_M
             and math.isfinite(row.truth_x) and row.truth_x <= IR_CONTACT_MAX_M),
            key=lambda row: row.truth_y)
        if len(skewed) < 3:
            reasons.append(
                f"{band}: fewer than three samples inside the contact band")
        else:
            diffs = [(b.ir_l - b.ir_r) - (a.ir_l - a.ir_r)
                     for a, b in zip(skewed, skewed[1:])]
            moved = [value for value in diffs if value != 0]
            if len(moved) < 3:
                reasons.append(f"{band}: skew never moved across the band")
            else:
                share = sum(1 for value in moved if value > 0) / len(moved)
                metrics[f"no_inversion_share_{band}"] = share
                if share < IR_NO_INVERSION_MIN:
                    reasons.append(
                        f"{band}: skew inverts in {1.0 - share:.0%} of the "
                        f"{len(moved)} moving pairs, no-inversion share "
                        f"{share:.0%} under {IR_NO_INVERSION_MIN:.0%}")

        responded = [row.truth_x for row in in_band
                     if row.dock_present and math.isfinite(row.truth_x)
                     and max((value for value in (row.ir_l, row.ir_mid, row.ir_r)
                              if value is not None), default=0) > threshold]
        if not responded:
            metrics[f"onset_m_{band}"] = math.nan
            # "온셋 0 mm 가 공차 안" 이라는 사유는 거리 문제처럼 읽힌다.
            # 실제로 일어난 일은 센서가 한 번도 응답하지 않은 것이다.
            reasons.append(
                f"{band}: no dock-present sample rose above the ambient floor "
                f"({floor} plus a {IR_FLOOR_MARGIN:.0%} margin) — the sensor "
                f"never responded")
        else:
            onset = max(responded)
            metrics[f"onset_m_{band}"] = onset
            if onset < IR_ONSET_MIN_M:
                reasons.append(
                    f"{band}: onset {onset * 1000:.0f} mm inside the "
                    f"{IR_ONSET_MIN_M * 1000:.0f} mm contact tolerance")

    return ProbeVerdict("ir", lane, not reasons, tuple(reasons), metrics)
