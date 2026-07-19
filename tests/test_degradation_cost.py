# BESS ProfitGuard: test_degradation_cost.py

from pathlib import Path

import pandas as pd

from backend.app.services.battery_health import BatteryHealthReport, calculate_battery_health
from backend.app.services.data_generator import SampleDataConfig, generate_sample_data
from backend.app.services.degradation_cost import calculate_degradation_cost
from backend.app.services.telemetry_validator import load_battery_config


def test_degradation_cost_report_calculates_net_benefit(tmp_path: Path) -> None:
    generate_sample_data(tmp_path, SampleDataConfig(days=1, seed=31))
    telemetry = pd.read_csv(tmp_path / "sample_bess_telemetry.csv")
    battery_config = load_battery_config(tmp_path / "sample_battery_config.csv")
    health_report = calculate_battery_health(telemetry, battery_config)

    report = calculate_degradation_cost(health_report, dict(battery_config), dispatch_revenue=5000.0)

    assert report.base_cycle_cost == 800.0
    assert report.stress_multiplier >= 1.0
    assert report.estimated_degradation_cost >= 0
    assert report.net_benefit == round(report.dispatch_revenue - report.estimated_degradation_cost, 2)
    assert report.recommendation in {"dispatch", "dispatch_with_caution", "preserve"}


def test_degradation_cost_preserves_when_revenue_is_too_low() -> None:
    health_report = BatteryHealthReport(
        estimated_soh_percent=95.0,
        equivalent_full_cycles=1.0,
        total_charge_energy_kwh=500.0,
        total_discharge_energy_kwh=450.0,
        net_energy_kwh=-50.0,
        max_c_rate=0.4,
        avg_c_rate_when_active=0.2,
        avg_temperature_c=29.0,
        max_temperature_c=34.0,
        high_temperature_hours=0.0,
        high_soc_dwell_hours=0.0,
        low_soc_dwell_hours=0.0,
        active_hours=4.0,
        stress_score=20.0,
        risk_level="low",
        risk_reasons=[],
    )
    config = {"replacement_cost": 4_000_000.0, "expected_cycle_life": 5_000.0}

    report = calculate_degradation_cost(health_report, config, dispatch_revenue=100.0)

    assert report.estimated_degradation_cost > report.dispatch_revenue
    assert report.recommendation == "preserve"
