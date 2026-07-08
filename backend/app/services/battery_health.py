from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class BatteryHealthThresholds:
    high_temperature_c: float = 35.0
    high_soc_percent: float = 85.0
    low_soc_percent: float = 15.0
    preferred_c_rate: float = 0.5
    stress_score_warn: float = 50.0
    stress_score_high: float = 75.0


@dataclass
class BatteryHealthReport:
    estimated_soh_percent: float
    equivalent_full_cycles: float
    total_charge_energy_kwh: float
    total_discharge_energy_kwh: float
    net_energy_kwh: float
    max_c_rate: float
    avg_c_rate_when_active: float
    avg_temperature_c: float
    max_temperature_c: float
    high_temperature_hours: float
    high_soc_dwell_hours: float
    low_soc_dwell_hours: float
    active_hours: float
    stress_score: float
    risk_level: str
    risk_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimated_soh_percent": self.estimated_soh_percent,
            "equivalent_full_cycles": self.equivalent_full_cycles,
            "total_charge_energy_kwh": self.total_charge_energy_kwh,
            "total_discharge_energy_kwh": self.total_discharge_energy_kwh,
            "net_energy_kwh": self.net_energy_kwh,
            "max_c_rate": self.max_c_rate,
            "avg_c_rate_when_active": self.avg_c_rate_when_active,
            "avg_temperature_c": self.avg_temperature_c,
            "max_temperature_c": self.max_temperature_c,
            "high_temperature_hours": self.high_temperature_hours,
            "high_soc_dwell_hours": self.high_soc_dwell_hours,
            "low_soc_dwell_hours": self.low_soc_dwell_hours,
            "active_hours": self.active_hours,
            "stress_score": self.stress_score,
            "risk_level": self.risk_level,
            "risk_reasons": self.risk_reasons,
        }


def _interval_hours(timestamps: pd.Series) -> float:
    parsed = pd.to_datetime(timestamps, errors="coerce").dropna().sort_values()
    if len(parsed) < 2:
        return 0.0
    median_delta = parsed.diff().dropna().median()
    return float(median_delta / pd.Timedelta(hours=1))


def _bounded_score(value: float, warning_value: float, severe_value: float, weight: float) -> float:
    if value <= 0:
        return 0.0
    if severe_value <= warning_value:
        return weight
    raw = (value - warning_value) / (severe_value - warning_value)
    return max(0.0, min(weight, raw * weight))


def calculate_battery_health(
    telemetry: pd.DataFrame,
    battery_config: pd.Series | dict[str, Any],
    thresholds: BatteryHealthThresholds | None = None,
) -> BatteryHealthReport:
    thresholds = thresholds or BatteryHealthThresholds()
    config = dict(battery_config)
    capacity_kwh = float(config["battery_capacity_kwh"])
    usable_capacity_kwh = float(config["usable_capacity_kwh"])
    expected_cycle_life = float(config["expected_cycle_life"])
    dt_hours = _interval_hours(telemetry["timestamp"])

    if dt_hours <= 0:
        raise ValueError("Telemetry must contain at least two valid timestamps with a regular interval.")

    frame = telemetry.copy()
    power_kw = frame["battery_power_kw"].astype(float)
    soc = frame["soc_percent"].astype(float)
    temperature = frame["temperature_c"].astype(float)
    c_rate = power_kw.abs() / capacity_kwh

    discharge_energy = (power_kw.clip(lower=0) * dt_hours).sum()
    charge_energy = ((-power_kw.clip(upper=0)) * dt_hours).sum()
    equivalent_full_cycles = discharge_energy / usable_capacity_kwh if usable_capacity_kwh else 0.0
    active_mask = power_kw.abs() > 1e-6

    high_temperature_hours = float((temperature > thresholds.high_temperature_c).sum() * dt_hours)
    high_soc_dwell_hours = float((soc > thresholds.high_soc_percent).sum() * dt_hours)
    low_soc_dwell_hours = float((soc < thresholds.low_soc_percent).sum() * dt_hours)
    active_hours = float(active_mask.sum() * dt_hours)
    high_c_rate_hours = float((c_rate > thresholds.preferred_c_rate).sum() * dt_hours)

    temp_score = _bounded_score(high_temperature_hours, 1.0, 8.0, 25.0)
    high_soc_score = _bounded_score(high_soc_dwell_hours, 4.0, 24.0, 25.0)
    low_soc_score = _bounded_score(low_soc_dwell_hours, 2.0, 12.0, 10.0)
    c_rate_score = _bounded_score(high_c_rate_hours, 0.5, 4.0, 20.0)
    cycle_score = _bounded_score(equivalent_full_cycles, 0.25, 1.5, 20.0)
    stress_score = round(min(100.0, temp_score + high_soc_score + low_soc_score + c_rate_score + cycle_score), 2)

    cycle_life_consumed_percent = (equivalent_full_cycles / expected_cycle_life * 100) if expected_cycle_life else 0.0
    stress_soh_penalty = stress_score * 0.015
    estimated_soh = max(70.0, 100.0 - cycle_life_consumed_percent - stress_soh_penalty)

    risk_reasons: list[str] = []
    if high_temperature_hours > 0:
        risk_reasons.append(f"Temperature exceeded {thresholds.high_temperature_c:g} C for {high_temperature_hours:.2f} hours.")
    if high_soc_dwell_hours > 0:
        risk_reasons.append(f"SoC stayed above {thresholds.high_soc_percent:g}% for {high_soc_dwell_hours:.2f} hours.")
    if low_soc_dwell_hours > 0:
        risk_reasons.append(f"SoC stayed below {thresholds.low_soc_percent:g}% for {low_soc_dwell_hours:.2f} hours.")
    if high_c_rate_hours > 0:
        risk_reasons.append(f"C-rate exceeded {thresholds.preferred_c_rate:g}C for {high_c_rate_hours:.2f} hours.")

    if stress_score >= thresholds.stress_score_high:
        risk_level = "high"
    elif stress_score >= thresholds.stress_score_warn:
        risk_level = "medium"
    else:
        risk_level = "low"

    avg_active_c_rate = float(c_rate[active_mask].mean()) if active_mask.any() else 0.0

    return BatteryHealthReport(
        estimated_soh_percent=round(float(estimated_soh), 2),
        equivalent_full_cycles=round(float(equivalent_full_cycles), 4),
        total_charge_energy_kwh=round(float(charge_energy), 3),
        total_discharge_energy_kwh=round(float(discharge_energy), 3),
        net_energy_kwh=round(float(discharge_energy - charge_energy), 3),
        max_c_rate=round(float(c_rate.max()), 4),
        avg_c_rate_when_active=round(avg_active_c_rate, 4),
        avg_temperature_c=round(float(temperature.mean()), 3),
        max_temperature_c=round(float(temperature.max()), 3),
        high_temperature_hours=round(high_temperature_hours, 3),
        high_soc_dwell_hours=round(high_soc_dwell_hours, 3),
        low_soc_dwell_hours=round(low_soc_dwell_hours, 3),
        active_hours=round(active_hours, 3),
        stress_score=stress_score,
        risk_level=risk_level,
        risk_reasons=risk_reasons,
    )
