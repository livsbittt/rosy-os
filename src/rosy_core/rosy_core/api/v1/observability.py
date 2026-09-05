"""rosy_core.api.v1.observability — EVT-003 이벤트, LOG-001 감사 로그, OBS-101 metrics."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from rosy_core.api.v1.common import admin, viewer
from rosy_core.api.deps import AuthContext, get_services
from rosy_core.services import CoreServices


events_router = APIRouter(prefix="/api/v1/events", tags=["events"])
logs_router = APIRouter(prefix="/api/v1/logs", tags=["logs"])


@events_router.get("")
def list_events(since_seq: int | None = None, limit: int = 100,
                _: AuthContext = Depends(viewer), svc: CoreServices = Depends(get_services)):
    events = svc.events.history(since_seq=since_seq, limit=limit)
    return {"events": [e.model_dump() for e in events], "last_seq": svc.events.last_seq}


@logs_router.get("/audit")
def list_audit_logs(
    since_seq: int | None = None,
    limit: int = 500,
    _: AuthContext = Depends(admin),
    svc: CoreServices = Depends(get_services),
):
    events = svc.audit.history(since_seq=since_seq, limit=min(limit, 2000))
    return {"events": [e.model_dump() for e in events]}

metrics_router = APIRouter(tags=["metrics"])

_HEALTH_VALUE = {"OK": 0, "UNKNOWN": 1, "WARNING": 2, "ERROR": 3}


@metrics_router.get("/metrics")
def metrics(svc: CoreServices = Depends(get_services)):
    import time as _time

    snap = svc.state.snapshot()
    lines = [
        "# HELP rosy_uptime_seconds rosy_core process uptime",
        "# TYPE rosy_uptime_seconds gauge",
        f"rosy_uptime_seconds {(_time.time() - svc.started_at):.1f}",
        "# HELP rosy_state_seq state snapshot sequence",
        "# TYPE rosy_state_seq counter",
        f"rosy_state_seq {snap.seq}",
        "# HELP rosy_events_published_total events published",
        "# TYPE rosy_events_published_total counter",
        f"rosy_events_published_total {svc.events.last_seq}",
        "# HELP rosy_battery_percent battery percent estimate",
        "# TYPE rosy_battery_percent gauge",
        f"rosy_battery_percent {snap.battery.percent if snap.battery.percent is not None else -1}",
        "# HELP rosy_diagnostics_health component health (0=OK,1=UNKNOWN,2=WARNING,3=ERROR)",
        "# TYPE rosy_diagnostics_health gauge",
    ]
    for component, health in snap.diagnostics_summary.items():
        lines.append(f'rosy_diagnostics_health{{component="{component}"}} {_HEALTH_VALUE[health.value]}')
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
