from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import linprog


@dataclass(frozen=True)
class DispatchOptimizerConfig:
    horizon_hours: int = 24
    freq: str = "1h"
    charge_efficiency: float = 0.95
    discharge_efficiency: float = 0.95
    initial_soc_percent: float = 50.0
    terminal_soc_percent: float = 50.0


@dataclass
class StrategySummary:
    strategy: str
    energy_cost: float
    gross_savings: float
    degradation_cost: float
    net_savings: float
    total_charge_energy_kwh: float
    total_discharge_energy_kwh: float
    final_soc_percent: float | None
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "energy_cost": self.energy_cost,
            "gross_savings": self.gross_savings,
            "degradation_cost": self.degradation_cost,
            "net_savings": self.net_savings,
            "total_charge_energy_kwh": self.total_charge_energy_kwh,
            "total_discharge_energy_kwh": self.total_discharge_energy_kwh,
            "final_soc_percent": self.final_soc_percent,
            "status": self.status,
        }


@dataclass
class DispatchComparisonReport:
    baseline: StrategySummary
    energy_cost_only: StrategySummary
    degradation_aware: StrategySummary
    recommendation: str
    schedule: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline": self.baseline.to_dict(),
            "energy_cost_only": self.energy_cost_only.to_dict(),
            "degradation_aware": self.degradation_aware.to_dict(),
            "recommendation": self.recommendation,
            "schedule": self.schedule,
        }


def _prepare_site_frame(
    site_load: pd.DataFrame,
    pv_generation: pd.DataFrame,
    tariff: pd.DataFrame,
    config: DispatchOptimizerConfig,
) -> pd.DataFrame:
    load = site_load.copy()
    pv = pv_generation.copy()
    prices = tariff.copy()
    for frame in (load, pv, prices):
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        frame.set_index("timestamp", inplace=True)

    frame = pd.concat(
        [
            load[["site_load_kw"]],
            pv[["pv_generation_kw"]],
            prices[["energy_price_per_kwh", "export_price_per_kwh"]],
        ],
        axis=1,
    ).sort_index()
    frame = frame.resample(config.freq).mean().dropna().head(config.horizon_hours)
    if len(frame) != config.horizon_hours:
        raise ValueError(f"Expected {config.horizon_hours} complete periods, got {len(frame)}.")
    return frame.reset_index()


def _battery_config_value(config: pd.Series | dict[str, Any], key: str) -> float:
    return float(dict(config)[key])


def calculate_no_battery_cost(site_frame: pd.DataFrame, dt_hours: float) -> float:
    net_load = site_frame["site_load_kw"] - site_frame["pv_generation_kw"]
    grid_import = net_load.clip(lower=0)
    export = (-net_load.clip(upper=0))
    cost = (
        grid_import * site_frame["energy_price_per_kwh"] * dt_hours
        - export * site_frame["export_price_per_kwh"] * dt_hours
    ).sum()
    return round(float(cost), 2)


def _solve_battery_dispatch(
    site_frame: pd.DataFrame,
    battery_config: pd.Series | dict[str, Any],
    degradation_cost_per_kwh: float,
    strategy_name: str,
    baseline_cost: float,
    optimizer_config: DispatchOptimizerConfig,
) -> tuple[StrategySummary, list[dict[str, Any]]]:
    n = len(site_frame)
    dt_hours = pd.Timedelta(optimizer_config.freq) / pd.Timedelta(hours=1)
    capacity_kwh = _battery_config_value(battery_config, "battery_capacity_kwh")
    max_charge_kw = _battery_config_value(battery_config, "max_charge_power_kw")
    max_discharge_kw = _battery_config_value(battery_config, "max_discharge_power_kw")
    min_soc_percent = max(
        _battery_config_value(battery_config, "min_soc_percent"),
        _battery_config_value(battery_config, "reserve_soc_percent"),
    )
    max_soc_percent = _battery_config_value(battery_config, "max_soc_percent")
    initial_soc_percent = optimizer_config.initial_soc_percent
    terminal_soc_percent = optimizer_config.terminal_soc_percent
    initial_energy_kwh = capacity_kwh * initial_soc_percent / 100
    terminal_energy_kwh = capacity_kwh * terminal_soc_percent / 100
    min_energy_kwh = capacity_kwh * min_soc_percent / 100
    max_energy_kwh = capacity_kwh * max_soc_percent / 100

    charge_offset = 0
    discharge_offset = n
    soc_offset = 2 * n
    grid_offset = 3 * n
    export_offset = 4 * n
    variable_count = 5 * n

    c = np.zeros(variable_count)
    c[grid_offset : grid_offset + n] = site_frame["energy_price_per_kwh"].to_numpy() * dt_hours
    c[export_offset : export_offset + n] = -site_frame["export_price_per_kwh"].to_numpy() * dt_hours
    c[discharge_offset : discharge_offset + n] = degradation_cost_per_kwh * dt_hours

    bounds = (
        [(0, max_charge_kw)] * n
        + [(0, max_discharge_kw)] * n
        + [(min_energy_kwh, max_energy_kwh)] * n
        + [(0, None)] * n
        + [(0, None)] * n
    )

    equalities: list[np.ndarray] = []
    rhs: list[float] = []

    for i in range(n):
        row = np.zeros(variable_count)
        row[grid_offset + i] = 1.0
        row[export_offset + i] = -1.0
        row[charge_offset + i] = -1.0
        row[discharge_offset + i] = 1.0
        equalities.append(row)
        rhs.append(float(site_frame.loc[i, "site_load_kw"] - site_frame.loc[i, "pv_generation_kw"]))

    for i in range(n):
        row = np.zeros(variable_count)
        row[soc_offset + i] = 1.0
        if i > 0:
            row[soc_offset + i - 1] = -1.0
            rhs_value = 0.0
        else:
            rhs_value = initial_energy_kwh
        row[charge_offset + i] = -optimizer_config.charge_efficiency * dt_hours
        row[discharge_offset + i] = (1 / optimizer_config.discharge_efficiency) * dt_hours
        equalities.append(row)
        rhs.append(rhs_value)

    terminal_row = np.zeros(variable_count)
    terminal_row[soc_offset + n - 1] = 1.0
    equalities.append(terminal_row)
    rhs.append(terminal_energy_kwh)

    result = linprog(
        c,
        A_eq=np.vstack(equalities),
        b_eq=np.asarray(rhs),
        bounds=bounds,
        method="highs",
    )
    if not result.success:
        summary = StrategySummary(
            strategy=strategy_name,
            energy_cost=0.0,
            gross_savings=0.0,
            degradation_cost=0.0,
            net_savings=0.0,
            total_charge_energy_kwh=0.0,
            total_discharge_energy_kwh=0.0,
            final_soc_percent=None,
            status=result.message,
        )
        return summary, []

    values = result.x
    charge = values[charge_offset : charge_offset + n]
    discharge = values[discharge_offset : discharge_offset + n]
    soc = values[soc_offset : soc_offset + n]
    grid_import = values[grid_offset : grid_offset + n]
    export = values[export_offset : export_offset + n]

    energy_cost = float(
        (
            grid_import * site_frame["energy_price_per_kwh"].to_numpy() * dt_hours
            - export * site_frame["export_price_per_kwh"].to_numpy() * dt_hours
        ).sum()
    )
    discharge_energy = float((discharge * dt_hours).sum())
    charge_energy = float((charge * dt_hours).sum())
    degradation_cost = float(discharge_energy * degradation_cost_per_kwh)
    gross_savings = baseline_cost - energy_cost
    net_savings = gross_savings - degradation_cost
    final_soc_percent = float(soc[-1] / capacity_kwh * 100)

    schedule: list[dict[str, Any]] = []
    for i in range(n):
        schedule.append(
            {
                "timestamp": str(site_frame.loc[i, "timestamp"]),
                "strategy": strategy_name,
                "charge_kw": round(float(charge[i]), 3),
                "discharge_kw": round(float(discharge[i]), 3),
                "soc_percent": round(float(soc[i] / capacity_kwh * 100), 3),
                "grid_import_kw": round(float(grid_import[i]), 3),
                "pv_export_kw": round(float(export[i]), 3),
                "energy_price_per_kwh": round(float(site_frame.loc[i, "energy_price_per_kwh"]), 3),
            }
        )

    summary = StrategySummary(
        strategy=strategy_name,
        energy_cost=round(energy_cost, 2),
        gross_savings=round(gross_savings, 2),
        degradation_cost=round(degradation_cost, 2),
        net_savings=round(net_savings, 2),
        total_charge_energy_kwh=round(charge_energy, 2),
        total_discharge_energy_kwh=round(discharge_energy, 2),
        final_soc_percent=round(final_soc_percent, 2),
        status="optimal",
    )
    return summary, schedule


def compare_dispatch_strategies(
    site_load: pd.DataFrame,
    pv_generation: pd.DataFrame,
    tariff: pd.DataFrame,
    battery_config: pd.Series | dict[str, Any],
    degradation_stress_multiplier: float = 1.0,
    optimizer_config: DispatchOptimizerConfig | None = None,
) -> DispatchComparisonReport:
    optimizer_config = optimizer_config or DispatchOptimizerConfig()
    site_frame = _prepare_site_frame(site_load, pv_generation, tariff, optimizer_config)
    dt_hours = pd.Timedelta(optimizer_config.freq) / pd.Timedelta(hours=1)
    baseline_cost = calculate_no_battery_cost(site_frame, dt_hours)
    baseline = StrategySummary(
        strategy="no_battery",
        energy_cost=baseline_cost,
        gross_savings=0.0,
        degradation_cost=0.0,
        net_savings=0.0,
        total_charge_energy_kwh=0.0,
        total_discharge_energy_kwh=0.0,
        final_soc_percent=None,
        status="calculated",
    )

    usable_capacity_kwh = _battery_config_value(battery_config, "usable_capacity_kwh")
    replacement_cost = _battery_config_value(battery_config, "replacement_cost")
    expected_cycle_life = _battery_config_value(battery_config, "expected_cycle_life")
    degradation_cost_per_kwh = (replacement_cost / expected_cycle_life) * degradation_stress_multiplier / usable_capacity_kwh

    cost_only, _ = _solve_battery_dispatch(
        site_frame=site_frame,
        battery_config=battery_config,
        degradation_cost_per_kwh=0.0,
        strategy_name="energy_cost_only",
        baseline_cost=baseline_cost,
        optimizer_config=optimizer_config,
    )
    cost_only.degradation_cost = round(cost_only.total_discharge_energy_kwh * degradation_cost_per_kwh, 2)
    cost_only.net_savings = round(cost_only.gross_savings - cost_only.degradation_cost, 2)

    degradation_aware, schedule = _solve_battery_dispatch(
        site_frame=site_frame,
        battery_config=battery_config,
        degradation_cost_per_kwh=degradation_cost_per_kwh,
        strategy_name="degradation_aware",
        baseline_cost=baseline_cost,
        optimizer_config=optimizer_config,
    )

    if degradation_aware.status != "optimal":
        recommendation = "Optimization failed; inspect inputs."
    elif degradation_aware.net_savings >= cost_only.net_savings:
        recommendation = "Use degradation-aware dispatch; it protects net value after battery lifetime cost."
    else:
        recommendation = "Energy-cost-only dispatch has higher modeled net value for this horizon; inspect degradation assumptions."

    return DispatchComparisonReport(
        baseline=baseline,
        energy_cost_only=cost_only,
        degradation_aware=degradation_aware,
        recommendation=recommendation,
        schedule=schedule,
    )
