from pathlib import Path

import pandas as pd

from backend.app.services.battery_health import calculate_battery_health
from backend.app.services.data_generator import SampleDataConfig, generate_sample_data
from backend.app.services.telemetry_validator import load_battery_config


def test_battery_health_report_has_expected_core_metrics(tmp_path: Path) -> None:
    generate_sample_data(tmp_path, SampleDataConfig(days=1, seed=21))
    telemetry = pd.read_csv(tmp_path / "sample_bess_telemetry.csv")
    battery_config = load_battery_config(tmp_path / "sample_battery_config.csv")

    report = calculate_battery_health(telemetry, battery_config)

    assert report.estimated_soh_percent <= 100
    assert report.estimated_soh_percent >= 70
    assert report.equivalent_full_cycles >= 0
    assert report.total_charge_energy_kwh >= 0
    assert report.total_discharge_energy_kwh >= 0
    assert report.max_c_rate <= 0.5
    assert 0 <= report.stress_score <= 100
    assert report.risk_level in {"low", "medium", "high"}


def test_battery_health_flags_high_stress_operation() -> None:
    telemetry = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=8, freq="15min"),
            "battery_voltage_v": [720.0] * 8,
            "battery_current_a": [347.0] * 8,
            "battery_power_kw": [250.0] * 8,
            "soc_percent": [90.0] * 8,
            "temperature_c": [39.0] * 8,
        }
    )
    config = {
        "battery_capacity_kwh": 500.0,
        "usable_capacity_kwh": 450.0,
        "expected_cycle_life": 5000.0,
    }

    report = calculate_battery_health(telemetry, config)

    assert report.high_temperature_hours == 2.0
    assert report.high_soc_dwell_hours == 2.0
    assert report.stress_score > 0
    assert report.risk_reasons
