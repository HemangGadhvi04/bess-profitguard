from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class EVReadinessSummary:
    ev_count: int
    ready_ev_count: int
    readiness_percent: float
    priority_ev_count: int
    priority_ready_ev_count: int
    priority_readiness_percent: float
    unmet_energy_kwh: float

    def to_dict(self) -> dict[str, float | int]:
        return {
            "ev_count": self.ev_count,
            "ready_ev_count": self.ready_ev_count,
            "readiness_percent": self.readiness_percent,
            "priority_ev_count": self.priority_ev_count,
            "priority_ready_ev_count": self.priority_ready_ev_count,
            "priority_readiness_percent": self.priority_readiness_percent,
            "unmet_energy_kwh": self.unmet_energy_kwh,
        }


def summarize_ev_readiness(
    ev_sessions: pd.DataFrame | None,
    unmet_energy_by_session: list[float] | None = None,
    priority_cutoff: int = 2,
) -> EVReadinessSummary:
    if ev_sessions is None or ev_sessions.empty:
        return EVReadinessSummary(
            ev_count=0,
            ready_ev_count=0,
            readiness_percent=100.0,
            priority_ev_count=0,
            priority_ready_ev_count=0,
            priority_readiness_percent=100.0,
            unmet_energy_kwh=0.0,
        )

    unmet = unmet_energy_by_session or [0.0] * len(ev_sessions)
    if len(unmet) != len(ev_sessions):
        raise ValueError("unmet_energy_by_session must match the number of EV sessions.")

    ready_flags = [value <= 1e-6 for value in unmet]
    priority_flags = [int(row.get("priority_level", 3)) <= priority_cutoff for _, row in ev_sessions.iterrows()]
    priority_count = sum(priority_flags)
    priority_ready = sum(ready for ready, priority in zip(ready_flags, priority_flags) if priority)
    ready_count = sum(ready_flags)

    return EVReadinessSummary(
        ev_count=len(ev_sessions),
        ready_ev_count=ready_count,
        readiness_percent=round(ready_count / len(ev_sessions) * 100, 2),
        priority_ev_count=priority_count,
        priority_ready_ev_count=priority_ready,
        priority_readiness_percent=round(priority_ready / priority_count * 100, 2) if priority_count else 100.0,
        unmet_energy_kwh=round(float(sum(unmet)), 3),
    )


def session_power_limit(session: pd.Series | dict[str, Any]) -> float:
    return float(dict(session)["max_charging_power_kw"])
