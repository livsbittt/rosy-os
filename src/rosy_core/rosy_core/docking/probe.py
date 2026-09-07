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
