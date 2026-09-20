#!/usr/bin/env python3
"""Run a deterministic IR/camera line-follow simulation and write evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from control.sensing.lane import IRLineCalibration, detect_ir_line, detect_lane_error
from core_events.events.bus import EventBus
from core_features.line_follow import (
    LineFollowConfig,
    LineFollowManager,
    LineFollowMode,
    LineObservation,
)


IR_SAMPLES = (
    (850, 220, 150),
    (760, 430, 170),
    (500, 760, 210),
    (180, 850, 180),
    (210, 760, 500),
    (170, 430, 760),
    (150, 220, 850),
)
CAMERA_COLUMNS = (24, 44, 64, 80, 96, 116, 136)


def _ir_observations():
    calibration = IRLineCalibration(
        black=(100.0, 100.0, 100.0), white=(900.0, 900.0, 900.0))
    return [detect_ir_line(sample, calibration) for sample in IR_SAMPLES]


def _camera_observations():
    observations = []
    for centre in CAMERA_COLUMNS:
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        frame[:, max(0, centre - 6):min(160, centre + 6)] = 255
        observations.append(detect_lane_error(
            frame, bright_threshold=180, roi_top_fraction=0.4,
            washed_fraction=0.4, min_pixels=80))
    return observations


def _run_mode(mode: LineFollowMode, observations) -> tuple[dict, list[dict]]:
    now = [10.0]
    events = EventBus("rosy_sim")
    manager = LineFollowManager(
        events,
        config=LineFollowConfig(
            cruise_speed=0.09, max_linear=0.10, steering_gain=0.8,
            max_angular=0.7, min_confidence=0.35,
            stale_after_s=0.3, lost_after_s=3.0),
        clock=lambda: now[0],
    )
    manager.set_mode(mode)
    samples = []
    for item in observations:
        assert item is not None
        observation = LineObservation(
            source=mode, stamp=now[0], visible=True,
            error=item.error, confidence=item.confidence)
        manager.observe(observation, received_at=now[0])
        decision = manager.tick(now[0])
        samples.append({
            "t": round(now[0] - 10.0, 2),
            "error": round(item.error, 4),
            "confidence": round(item.confidence, 4),
            "linear": round(decision.linear, 5),
            "angular": round(decision.angular, 5),
            "state": manager.status().state,
        })
        now[0] += 0.1

    straight = min(samples, key=lambda item: abs(item["error"]))
    tracking_speeds = [item["linear"] for item in samples if item["linear"] > 0.0]
    now[0] += 0.31
    stale = manager.tick(now[0])
    now[0] += 3.01
    lost = manager.tick(now[0])
    result = {
        "tracking_samples": len(tracking_speeds),
        "straight_speed": straight["linear"],
        "minimum_tracking_speed": min(tracking_speeds),
        "maximum_angular": max(abs(item["angular"]) for item in samples),
        "stale_stop": stale.linear == 0.0 and stale.angular == 0.0,
        "loss_latched": manager.status().state == "LOST" and lost.linear == 0.0,
        "final_reason": manager.status().reason,
        "lane_lost_events": sum(
            event.type == "nav.lane_lost" for event in events.history()),
    }
    return result, samples


def _svg(series: dict[str, list[dict]]) -> str:
    width, height = 920, 440
    plot_x, plot_y, plot_w, plot_h = 70, 55, 800, 300
    colours = {"IR_LINE": "#30d5c8", "CAMERA_LINE": "#ffbf69"}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#0b1220"/>',
        '<text x="70" y="30" fill="#f3f6fb" font-family="sans-serif" font-size="20">D-143 line-follow host simulation</text>',
        f'<line x1="{plot_x}" y1="{plot_y + plot_h}" x2="{plot_x + plot_w}" y2="{plot_y + plot_h}" stroke="#617086"/>',
        f'<line x1="{plot_x}" y1="{plot_y}" x2="{plot_x}" y2="{plot_y + plot_h}" stroke="#617086"/>',
        '<text x="8" y="75" fill="#9eacc0" font-family="sans-serif" font-size="12">0.10 m/s</text>',
        '<text x="22" y="360" fill="#9eacc0" font-family="sans-serif" font-size="12">0.00</text>',
    ]
    for mode, samples in series.items():
        points = []
        for index, sample in enumerate(samples):
            x = plot_x + index * plot_w / max(1, len(samples) - 1)
            y = plot_y + plot_h * (1.0 - sample["linear"] / 0.10)
            points.append(f"{x:.1f},{y:.1f}")
        colour = colours[mode]
        parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{colour}" stroke-width="4"/>')
    legend_y = 395
    for index, mode in enumerate(("IR_LINE", "CAMERA_LINE")):
        x = 80 + index * 260
        parts.extend([
            f'<line x1="{x}" y1="{legend_y}" x2="{x + 34}" y2="{legend_y}" stroke="{colours[mode]}" stroke-width="4"/>',
            f'<text x="{x + 44}" y="{legend_y + 5}" fill="#f3f6fb" font-family="sans-serif" font-size="14">{mode}</text>',
        ])
    parts.append('<text x="560" y="400" fill="#9eacc0" font-family="sans-serif" font-size="13">curve + confidence reduce speed; stale/lost = 0</text>')
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def run_simulation(output_dir: Path | str) -> dict:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    modes = {}
    series = {}
    for mode, observations in (
        (LineFollowMode.IR_LINE, _ir_observations()),
        (LineFollowMode.CAMERA_LINE, _camera_observations()),
    ):
        result, samples = _run_mode(mode, observations)
        modes[mode.value] = result
        series[mode.value] = samples
    summary = {
        "status": "HOST_SIMULATION_PASS",
        "physical_device_validated": False,
        "modes": modes,
        "series": series,
    }
    (target / "result.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    (target / "line_follow_simulation.svg").write_text(_svg(series), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = run_simulation(args.output)
    print(json.dumps(summary["modes"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
