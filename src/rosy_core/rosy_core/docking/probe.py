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
