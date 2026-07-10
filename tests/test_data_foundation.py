from pathlib import Path

import pandas as pd

from backend.app.services.battery_health import calculate_battery_health
from backend.app.services.data_generator import SampleDataConfig, generate_sample_data
from backend.app.services.degradation_cost import calculate_degradation_cost
from backend.app.services.dispatch_optimizer import compare_dispatch_strategies
from backend.app.services.telemetry_validator import validate_generated_dataset

def test_generate_sample_data_creates_expected_files(tmp_path: Path) -> None:
    written = generate_sample_data(tmp_path, SampleDataConfig(days=1, seed=7))
    expected = {
        "sample_site_load",
        "sample_pv_generation",
        "sample_tariff",
        "sample_ev_sessions",
        "sample_bess_telemetry",
        "sample_battery_config",
    }
    assert set(written) == expected
    for path in written.values():
        assert path.exists()
    telemetry = pd.read_csv(written["sample_bess_telemetry"])
    assert len(telemetry) == 96
    assert telemetry["soc_percent"].between(0, 100).all()

def test_generated_dataset_validation_passes_without_errors(tmp_path: Path) -> None:
    generate_sample_data(tmp_path, SampleDataConfig(days=1, seed=11))
    reports = validate_generated_dataset(tmp_path)
    assert reports
    assert all(report.passed for report in reports)


def test_validator_detects_invalid_soc(tmp_path: Path) -> None:
    written = generate_sample_data(tmp_path, SampleDataConfig(days=1, seed=42))
    # intentionally corrupt SOC
    df = pd.read_csv(written["sample_bess_telemetry"])
    df.loc[0, "soc_percent"] = 150.0
    df.to_csv(written["sample_bess_telemetry"], index=False)

    reports = validate_generated_dataset(tmp_path)
    bess_report = next(r for r in reports if r.dataset == "bess_telemetry")
    assert not bess_report.passed
    assert any("soc" in issue.message.lower() for issue in bess_report.issues if issue.severity == "error")


def test_battery_health_calculates_efc(tmp_path: Path) -> None:
    written = generate_sample_data(tmp_path, SampleDataConfig(days=1, seed=42))
    df = pd.read_csv(written["sample_bess_telemetry"])
    battery_config = pd.read_csv(written["sample_battery_config"]).iloc[0].to_dict()
    health = calculate_battery_health(df, battery_config)
    assert health.equivalent_full_cycles > 0


def test_degradation_cost_positive(tmp_path: Path) -> None:
    written = generate_sample_data(tmp_path, SampleDataConfig(days=1, seed=42))
    df = pd.read_csv(written["sample_bess_telemetry"])
    battery_config = pd.read_csv(written["sample_battery_config"]).iloc[0].to_dict()
    health = calculate_battery_health(df, battery_config)
    deg_cost = calculate_degradation_cost(health, battery_config, dispatch_revenue=100)
    assert deg_cost.estimated_degradation_cost > 0


def test_dispatch_optimizer_returns_three_strategies(tmp_path: Path) -> None:
    written = generate_sample_data(tmp_path, SampleDataConfig(days=1, seed=42))
    site_load = pd.read_csv(written["sample_site_load"])
    pv_generation = pd.read_csv(written["sample_pv_generation"])
    tariff = pd.read_csv(written["sample_tariff"])
    battery_config = pd.read_csv(written["sample_battery_config"]).iloc[0].to_dict()

    report = compare_dispatch_strategies(site_load, pv_generation, tariff, battery_config)
    assert report.baseline.strategy == "no_battery"
    assert report.energy_cost_only.strategy == "energy_cost_only"
    assert report.degradation_aware.strategy == "degradation_aware"


def test_degradation_aware_respects_soc_limits(tmp_path: Path) -> None:
    written = generate_sample_data(tmp_path, SampleDataConfig(days=1, seed=42))
    site_load = pd.read_csv(written["sample_site_load"])
    pv_generation = pd.read_csv(written["sample_pv_generation"])
    tariff = pd.read_csv(written["sample_tariff"])
    battery_config = pd.read_csv(written["sample_battery_config"]).iloc[0].to_dict()

    report = compare_dispatch_strategies(site_load, pv_generation, tariff, battery_config)
    for step in report.schedule:
        assert battery_config["min_soc_percent"] <= step["soc_percent"] <= battery_config["max_soc_percent"]


def test_ev_infeasible_session_warning(tmp_path: Path) -> None:
    written = generate_sample_data(tmp_path, SampleDataConfig(days=1, seed=42))
    ev_df = pd.read_csv(written["sample_ev_sessions"])
    ev_df.loc[0, "required_energy_kwh"] = 500.0
    ev_df.to_csv(written["sample_ev_sessions"], index=False)

    reports = validate_generated_dataset(tmp_path)
    ev_report = next(r for r in reports if r.dataset == "ev_sessions")
    assert len(ev_report.issues) > 0
