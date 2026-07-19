# BESS ProfitGuard Dispatch Optimizer

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import linprog

from backend.app.services.demand_charge import calculate_demand_charge_cost
from backend.app.services.ev_scheduler import summarize_ev_readiness
from backend.app.services.operating_modes import OperatingModeConfig, get_operating_mode


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
    peak_grid_import_kw: float = 0.0
    demand_charge_cost: float = 0.0
    peak_shaving_savings: float = 0.0
    ev_readiness_percent: float = 100.0
    priority_ev_readiness_percent: float = 100.0
    unmet_ev_energy_kwh: float = 0.0

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
            "peak_grid_import_kw": self.peak_grid_import_kw,
            "demand_charge_cost": self.demand_charge_cost,
            "peak_shaving_savings": self.peak_shaving_savings,
            "ev_readiness_percent": self.ev_readiness_percent,
            "priority_ev_readiness_percent": self.priority_ev_readiness_percent,
            "unmet_ev_energy_kwh": self.unmet_ev_energy_kwh,
        }


@dataclass
class DispatchComparisonReport:
    baseline: StrategySummary
    energy_cost_only: StrategySummary
    degradation_aware: StrategySummary
    recommendation: str
    schedule: list[dict[str, Any]]
    operating_mode: str = "profit_mode"

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline": self.baseline.to_dict(),
            "energy_cost_only": self.energy_cost_only.to_dict(),
            "degradation_aware": self.degradation_aware.to_dict(),
            "recommendation": self.recommendation,
            "schedule": self.schedule,
            "operating_mode": self.operating_mode,
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
            prices[["energy_price_per_kwh", "export_price_per_kwh", "demand_charge_per_kw"]],
        ],
        axis=1,
    ).sort_index()
    frame = frame.resample(config.freq).mean().dropna().head(config.horizon_hours)
    if len(frame) != config.horizon_hours:
        raise ValueError(f"Expected {config.horizon_hours} complete periods, got {len(frame)}.")
    return frame.reset_index()


def _battery_config_value(config: pd.Series | dict[str, Any], key: str) -> float:
    return float(dict(config)[key])


def _filter_ev_sessions_to_horizon(site_frame: pd.DataFrame, ev_sessions: pd.DataFrame | None) -> pd.DataFrame | None:
    if ev_sessions is None or ev_sessions.empty:
        return ev_sessions
    start = pd.to_datetime(site_frame["timestamp"].min())
    end = pd.to_datetime(site_frame["timestamp"].max()) + (site_frame["timestamp"].iloc[1] - site_frame["timestamp"].iloc[0])
    sessions = ev_sessions.copy()
    arrival = pd.to_datetime(sessions["arrival_time"])
    departure = pd.to_datetime(sessions["departure_time"])
    due_in_horizon = (arrival < end) & (departure > start) & (departure <= end)
    return sessions.loc[due_in_horizon].reset_index(drop=True)


def calculate_no_battery_profile(
    site_frame: pd.DataFrame,
    dt_hours: float,
    ev_sessions: pd.DataFrame | None = None,
) -> tuple[float, float, float]:
    net_load = site_frame["site_load_kw"] - site_frame["pv_generation_kw"]
    
    # If EV sessions exist, assume they charge at uniform rate over their connection window
    # in the baseline scenario to meet their required energy.
    ev_load = np.zeros(len(site_frame))
    if ev_sessions is not None and not ev_sessions.empty:
        site_timestamps = site_frame["timestamp"].values
        for _, session in ev_sessions.iterrows():
            arr = pd.to_datetime(session["arrival_time"])
            dep = pd.to_datetime(session["departure_time"])
            req_energy = session["required_energy_kwh"]
            # Find eligible timesteps
            eligible = (site_frame["timestamp"] >= arr) & (site_frame["timestamp"] < dep)
            num_eligible = eligible.sum()
            if num_eligible > 0:
                power = (req_energy / dt_hours) / num_eligible
                ev_load[eligible] += power
    
    net_load += ev_load
    grid_import = net_load.clip(lower=0)
    export = (-net_load.clip(upper=0))
    
    energy_cost = (
        grid_import * site_frame["energy_price_per_kwh"] * dt_hours
        - export * site_frame["export_price_per_kwh"] * dt_hours
    ).sum()
    
    peak_import = grid_import.max() if len(grid_import) > 0 else 0
    # Average demand charge over the period for calculation
    demand_cost = calculate_demand_charge_cost(peak_import, site_frame["demand_charge_per_kw"].mean())
    
    cost = energy_cost + demand_cost
    return round(float(cost), 2), round(float(peak_import), 3), round(float(demand_cost), 2)


def calculate_no_battery_cost(site_frame: pd.DataFrame, dt_hours: float, ev_sessions: pd.DataFrame | None = None) -> float:
    cost, _, _ = calculate_no_battery_profile(site_frame, dt_hours, ev_sessions)
    return cost


def _solve_battery_dispatch(
    site_frame: pd.DataFrame,
    battery_config: pd.Series | dict[str, Any],
    degradation_cost_per_kwh: float,
    strategy_name: str,
    baseline_cost: float,
    optimizer_config: DispatchOptimizerConfig,
    ev_sessions: pd.DataFrame | None = None,
    mode_config: OperatingModeConfig | None = None,
) -> tuple[StrategySummary, list[dict[str, Any]]]:
    mode_config = mode_config or get_operating_mode("profit_mode")
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

    has_ev = ev_sessions is not None and not ev_sessions.empty
    m = len(ev_sessions) if has_ev else 0

    charge_offset = 0
    discharge_offset = n
    soc_offset = 2 * n
    grid_offset = 3 * n
    export_offset = 4 * n
    peak_offset = 5 * n
    ev_offset = 5 * n + 1
    unmet_ev_offset = 5 * n + 1 + n * m
    variable_count = 5 * n + 1 + n * m + m

    c = np.zeros(variable_count)
    c[grid_offset : grid_offset + n] = site_frame["energy_price_per_kwh"].to_numpy() * dt_hours
    c[export_offset : export_offset + n] = -site_frame["export_price_per_kwh"].to_numpy() * dt_hours
    c[discharge_offset : discharge_offset + n] = degradation_cost_per_kwh * dt_hours
    
    # Add demand charge
    mean_demand_charge = float(site_frame["demand_charge_per_kw"].mean())
    c[peak_offset] = mean_demand_charge

    # Penalize unmet EV energy heavily
    if has_ev:
        for j in range(m):
            c[unmet_ev_offset + j] = mode_config.ev_unmet_penalty_per_kwh

    bounds = (
        [(0, max_charge_kw)] * n
        + [(0, max_discharge_kw)] * n
        + [(min_energy_kwh, max_energy_kwh)] * n
        + [(0, None)] * n
        + [(0, None)] * n
        + [(0, None)] # peak_import
    )

    if has_ev:
        for j in range(m):
            max_p = float(ev_sessions.iloc[j]["max_charging_power_kw"])
            bounds.extend([(0, max_p)] * n)
        bounds.extend([(0, None)] * m) # unmet_ev_energy bounds

    equalities: list[np.ndarray] = []
    rhs_eq: list[float] = []
    
    inequalities: list[np.ndarray] = []
    rhs_ineq: list[float] = []

    for i in range(n):
        row = np.zeros(variable_count)
        row[grid_offset + i] = 1.0
        row[export_offset + i] = -1.0
        row[charge_offset + i] = -1.0
        row[discharge_offset + i] = 1.0
        if has_ev:
            for j in range(m):
                row[ev_offset + j * n + i] = -1.0 # EV charging acts like site load
        
        equalities.append(row)
        rhs_eq.append(float(site_frame.loc[i, "site_load_kw"] - site_frame.loc[i, "pv_generation_kw"]))

        # Peak import constraint: grid_import[i] <= peak_import  ==> grid_import[i] - peak_import <= 0
        peak_row = np.zeros(variable_count)
        peak_row[grid_offset + i] = 1.0
        peak_row[peak_offset] = -1.0
        inequalities.append(peak_row)
        rhs_ineq.append(0.0)

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
        rhs_eq.append(rhs_value)

    terminal_row = np.zeros(variable_count)
    terminal_row[soc_offset + n - 1] = 1.0
    equalities.append(terminal_row)
    rhs_eq.append(terminal_energy_kwh)
    
    if has_ev:
        for j in range(m):
            session = ev_sessions.iloc[j]
            arr = pd.to_datetime(session["arrival_time"])
            dep = pd.to_datetime(session["departure_time"])
            req_energy = session["required_energy_kwh"]
            
            # Sum of ev_charge[i, j] * dt_hours + unmet[j] = req_energy
            ev_row = np.zeros(variable_count)
            for i in range(n):
                ts = site_frame.loc[i, "timestamp"]
                if arr <= ts < dep:
                    ev_row[ev_offset + j * n + i] = dt_hours
                else:
                    # force to zero outside window
                    z_row = np.zeros(variable_count)
                    z_row[ev_offset + j * n + i] = 1.0
                    equalities.append(z_row)
                    rhs_eq.append(0.0)
            ev_row[unmet_ev_offset + j] = 1.0
            equalities.append(ev_row)
            rhs_eq.append(req_energy)

    A_eq = np.vstack(equalities) if equalities else None
    b_eq = np.asarray(rhs_eq) if rhs_eq else None
    A_ub = np.vstack(inequalities) if inequalities else None
    b_ub = np.asarray(rhs_ineq) if rhs_ineq else None

    result = linprog(
        c,
        A_eq=A_eq,
        b_eq=b_eq,
        A_ub=A_ub,
        b_ub=b_ub,
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
            peak_grid_import_kw=0.0,
            demand_charge_cost=0.0,
            peak_shaving_savings=0.0,
            ev_readiness_percent=0.0 if has_ev else 100.0,
            priority_ev_readiness_percent=0.0 if has_ev else 100.0,
            unmet_ev_energy_kwh=0.0,
        )
        return summary, []

    values = result.x
    charge = values[charge_offset : charge_offset + n]
    discharge = values[discharge_offset : discharge_offset + n]
    soc = values[soc_offset : soc_offset + n]
    grid_import = values[grid_offset : grid_offset + n]
    export = values[export_offset : export_offset + n]
    peak_import_val = values[peak_offset]
    
    total_ev_charge = np.zeros(n)
    unmet_ev = []
    if has_ev:
        for j in range(m):
            total_ev_charge += values[ev_offset + j * n : ev_offset + (j + 1) * n]
        unmet_ev = [round(float(value), 6) for value in values[unmet_ev_offset : unmet_ev_offset + m]]
    ev_readiness = summarize_ev_readiness(ev_sessions, unmet_ev)

    energy_cost = float(
        (
            grid_import * site_frame["energy_price_per_kwh"].to_numpy() * dt_hours
            - export * site_frame["export_price_per_kwh"].to_numpy() * dt_hours
        ).sum()
    ) + peak_import_val * mean_demand_charge
    
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
                "ev_charge_kw": round(float(total_ev_charge[i]), 3) if has_ev else 0.0,
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
        peak_grid_import_kw=round(float(peak_import_val), 3),
        demand_charge_cost=round(float(peak_import_val * mean_demand_charge), 2),
        ev_readiness_percent=ev_readiness.readiness_percent,
        priority_ev_readiness_percent=ev_readiness.priority_readiness_percent,
        unmet_ev_energy_kwh=ev_readiness.unmet_energy_kwh,
    )
    return summary, schedule


def compare_dispatch_strategies(
    site_load: pd.DataFrame,
    pv_generation: pd.DataFrame,
    tariff: pd.DataFrame,
    battery_config: pd.Series | dict[str, Any],
    degradation_stress_multiplier: float = 1.0,
    optimizer_config: DispatchOptimizerConfig | None = None,
    ev_sessions: pd.DataFrame | None = None,
    operating_mode: str = "profit_mode",
) -> DispatchComparisonReport:
    optimizer_config = optimizer_config or DispatchOptimizerConfig()
    mode_config = get_operating_mode(operating_mode)
    if "demand_charge_per_kw" not in tariff.columns:
        tariff["demand_charge_per_kw"] = 0.0
    
    site_frame = _prepare_site_frame(site_load, pv_generation, tariff, optimizer_config)
    ev_sessions = _filter_ev_sessions_to_horizon(site_frame, ev_sessions)
    dt_hours = pd.Timedelta(optimizer_config.freq) / pd.Timedelta(hours=1)
    
    baseline_cost, baseline_peak, baseline_demand_cost = calculate_no_battery_profile(site_frame, dt_hours, ev_sessions)
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
        peak_grid_import_kw=baseline_peak,
        demand_charge_cost=baseline_demand_cost,
        ev_readiness_percent=100.0,
        priority_ev_readiness_percent=100.0,
        unmet_ev_energy_kwh=0.0,
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
        ev_sessions=ev_sessions,
        mode_config=mode_config,
    )
    cost_only.degradation_cost = round(cost_only.total_discharge_energy_kwh * degradation_cost_per_kwh, 2)
    cost_only.net_savings = round(cost_only.gross_savings - cost_only.degradation_cost, 2)
    cost_only.peak_shaving_savings = round(max(0.0, baseline.demand_charge_cost - cost_only.demand_charge_cost), 2)

    degradation_aware, schedule = _solve_battery_dispatch(
        site_frame=site_frame,
        battery_config=battery_config,
        degradation_cost_per_kwh=degradation_cost_per_kwh * mode_config.degradation_penalty_multiplier,
        strategy_name="degradation_aware",
        baseline_cost=baseline_cost,
        optimizer_config=optimizer_config,
        ev_sessions=ev_sessions,
        mode_config=mode_config,
    )
    degradation_aware.peak_shaving_savings = round(max(0.0, baseline.demand_charge_cost - degradation_aware.demand_charge_cost), 2)

    if degradation_aware.status != "optimal":
        recommendation = "Optimization failed; inspect inputs."
    elif degradation_aware.ev_readiness_percent < 100:
        recommendation = "EV readiness risk detected; use EV readiness mode or inspect infeasible sessions."
    elif degradation_aware.net_savings >= cost_only.net_savings:
        recommendation = f"Use degradation-aware dispatch in {mode_config.label}; it protects net value after battery lifetime cost."
    else:
        recommendation = "Energy-cost-only dispatch has higher modeled net value for this horizon; inspect degradation assumptions."

    return DispatchComparisonReport(
        baseline=baseline,
        energy_cost_only=cost_only,
        degradation_aware=degradation_aware,
        recommendation=recommendation,
        schedule=schedule,
        operating_mode=mode_config.name,
    )
