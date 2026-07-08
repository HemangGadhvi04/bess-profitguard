from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.services.battery_health import BatteryHealthReport


@dataclass(frozen=True)
class DegradationCostPolicy:
    currency: str = "INR"
    temperature_reference_hours: float = 8.0
    high_soc_reference_hours: float = 24.0
    low_soc_reference_hours: float = 12.0
    c_rate_reference: float = 0.5
    stress_score_reference: float = 100.0
    max_stress_multiplier: float = 2.5
    min_dispatch_margin_percent: float = 10.0


@dataclass
class DegradationCostReport:
    currency: str
    replacement_cost: float
    expected_cycle_life: float
    base_cycle_cost: float
    equivalent_full_cycles: float
    stress_multiplier: float
    temperature_multiplier: float
    soc_dwell_multiplier: float
    c_rate_multiplier: float
    soh_multiplier: float
    estimated_degradation_cost: float
    dispatch_revenue: float
    net_benefit: float
    recommendation: str
    confidence: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "currency": self.currency,
            "replacement_cost": self.replacement_cost,
            "expected_cycle_life": self.expected_cycle_life,
            "base_cycle_cost": self.base_cycle_cost,
            "equivalent_full_cycles": self.equivalent_full_cycles,
            "stress_multiplier": self.stress_multiplier,
            "temperature_multiplier": self.temperature_multiplier,
            "soc_dwell_multiplier": self.soc_dwell_multiplier,
            "c_rate_multiplier": self.c_rate_multiplier,
            "soh_multiplier": self.soh_multiplier,
            "estimated_degradation_cost": self.estimated_degradation_cost,
            "dispatch_revenue": self.dispatch_revenue,
            "net_benefit": self.net_benefit,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "reasons": self.reasons,
        }


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _as_float(config: dict[str, Any], key: str) -> float:
    if key not in config:
        raise KeyError(f"Battery config is missing required key: {key}")
    return float(config[key])


def calculate_degradation_cost(
    health_report: BatteryHealthReport,
    battery_config: dict[str, Any],
    dispatch_revenue: float,
    policy: DegradationCostPolicy | None = None,
) -> DegradationCostReport:
    policy = policy or DegradationCostPolicy()
    replacement_cost = _as_float(battery_config, "replacement_cost")
    expected_cycle_life = _as_float(battery_config, "expected_cycle_life")
    if replacement_cost <= 0:
        raise ValueError("replacement_cost must be positive.")
    if expected_cycle_life <= 0:
        raise ValueError("expected_cycle_life must be positive.")

    base_cycle_cost = replacement_cost / expected_cycle_life
    temperature_multiplier = 1.0 + _clamp(
        health_report.high_temperature_hours / policy.temperature_reference_hours,
        0.0,
        1.0,
    ) * 0.35
    soc_dwell_hours = health_report.high_soc_dwell_hours + health_report.low_soc_dwell_hours
    soc_dwell_multiplier = 1.0 + _clamp(soc_dwell_hours / policy.high_soc_reference_hours, 0.0, 1.0) * 0.30
    c_rate_multiplier = 1.0 + _clamp(
        max(0.0, health_report.max_c_rate - policy.c_rate_reference) / policy.c_rate_reference,
        0.0,
        1.0,
    ) * 0.25
    soh_multiplier = 1.0 + _clamp((100.0 - health_report.estimated_soh_percent) / 20.0, 0.0, 1.0) * 0.25
    stress_score_multiplier = 1.0 + _clamp(
        health_report.stress_score / policy.stress_score_reference,
        0.0,
        1.0,
    ) * 0.20

    stress_multiplier = temperature_multiplier * soc_dwell_multiplier * c_rate_multiplier * soh_multiplier * stress_score_multiplier
    stress_multiplier = _clamp(stress_multiplier, 1.0, policy.max_stress_multiplier)
    estimated_degradation_cost = health_report.equivalent_full_cycles * base_cycle_cost * stress_multiplier
    net_benefit = dispatch_revenue - estimated_degradation_cost

    required_margin = estimated_degradation_cost * (policy.min_dispatch_margin_percent / 100)
    if net_benefit > required_margin:
        recommendation = "dispatch"
    elif net_benefit >= 0:
        recommendation = "dispatch_with_caution"
    else:
        recommendation = "preserve"

    confidence = "medium"
    reasons: list[str] = []
    if health_report.risk_level == "high":
        confidence = "low"
        reasons.append("Battery stress risk is high, so the degradation estimate should be treated conservatively.")
    elif health_report.risk_level == "low":
        confidence = "medium-high"

    if recommendation == "dispatch":
        reasons.append("Estimated financial value exceeds degradation cost with margin.")
    elif recommendation == "dispatch_with_caution":
        reasons.append("Dispatch is net-positive but margin is thin after degradation cost.")
    else:
        reasons.append("Estimated degradation cost exceeds dispatch revenue.")

    if health_report.high_temperature_hours > 0:
        reasons.append("High-temperature exposure increased degradation cost.")
    if soc_dwell_hours > 0:
        reasons.append("High/low SoC dwell increased degradation cost.")
    if health_report.max_c_rate > policy.c_rate_reference:
        reasons.append("High C-rate operation increased degradation cost.")

    return DegradationCostReport(
        currency=policy.currency,
        replacement_cost=round(replacement_cost, 2),
        expected_cycle_life=round(expected_cycle_life, 2),
        base_cycle_cost=round(base_cycle_cost, 2),
        equivalent_full_cycles=health_report.equivalent_full_cycles,
        stress_multiplier=round(stress_multiplier, 4),
        temperature_multiplier=round(temperature_multiplier, 4),
        soc_dwell_multiplier=round(soc_dwell_multiplier, 4),
        c_rate_multiplier=round(c_rate_multiplier, 4),
        soh_multiplier=round(soh_multiplier, 4),
        estimated_degradation_cost=round(float(estimated_degradation_cost), 2),
        dispatch_revenue=round(float(dispatch_revenue), 2),
        net_benefit=round(float(net_benefit), 2),
        recommendation=recommendation,
        confidence=confidence,
        reasons=reasons,
    )
