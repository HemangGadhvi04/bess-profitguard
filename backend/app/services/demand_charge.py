from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DemandChargeMetrics:
    baseline_peak_grid_import_kw: float
    optimized_peak_grid_import_kw: float
    demand_charge_rate_per_kw: float
    baseline_demand_charge_cost: float
    optimized_demand_charge_cost: float
    peak_shaving_kw: float
    peak_shaving_savings: float
    monthly_peak_shaving_savings: float

    def to_dict(self) -> dict[str, float]:
        return {
            "baseline_peak_grid_import_kw": self.baseline_peak_grid_import_kw,
            "optimized_peak_grid_import_kw": self.optimized_peak_grid_import_kw,
            "demand_charge_rate_per_kw": self.demand_charge_rate_per_kw,
            "baseline_demand_charge_cost": self.baseline_demand_charge_cost,
            "optimized_demand_charge_cost": self.optimized_demand_charge_cost,
            "peak_shaving_kw": self.peak_shaving_kw,
            "peak_shaving_savings": self.peak_shaving_savings,
            "monthly_peak_shaving_savings": self.monthly_peak_shaving_savings,
        }


def calculate_demand_charge_cost(peak_grid_import_kw: float, demand_charge_rate_per_kw: float) -> float:
    return round(max(0.0, float(peak_grid_import_kw)) * max(0.0, float(demand_charge_rate_per_kw)), 2)


def compare_demand_charge(
    baseline_peak_grid_import_kw: float,
    optimized_peak_grid_import_kw: float,
    demand_charge_rate_per_kw: float,
    billing_days_per_month: int = 30,
) -> DemandChargeMetrics:
    baseline_cost = calculate_demand_charge_cost(baseline_peak_grid_import_kw, demand_charge_rate_per_kw)
    optimized_cost = calculate_demand_charge_cost(optimized_peak_grid_import_kw, demand_charge_rate_per_kw)
    peak_shaving_kw = max(0.0, float(baseline_peak_grid_import_kw) - float(optimized_peak_grid_import_kw))
    savings = max(0.0, baseline_cost - optimized_cost)
    return DemandChargeMetrics(
        baseline_peak_grid_import_kw=round(float(baseline_peak_grid_import_kw), 3),
        optimized_peak_grid_import_kw=round(float(optimized_peak_grid_import_kw), 3),
        demand_charge_rate_per_kw=round(float(demand_charge_rate_per_kw), 2),
        baseline_demand_charge_cost=baseline_cost,
        optimized_demand_charge_cost=optimized_cost,
        peak_shaving_kw=round(peak_shaving_kw, 3),
        peak_shaving_savings=round(savings, 2),
        monthly_peak_shaving_savings=round(savings * billing_days_per_month, 2),
    )
