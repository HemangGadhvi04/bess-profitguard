from pathlib import Path

import pandas as pd

from backend.app.services.battery_health import calculate_battery_health
from backend.app.services.data_generator import SampleDataConfig, generate_sample_data
from backend.app.services.degradation_cost import calculate_degradation_cost
from backend.app.services.dispatch_optimizer import compare_dispatch_strategies
from backend.app.services.telemetry_validator import load_battery_config


def test_dispatch_optimizer_compares_three_strategies(tmp_path: Path) -> None:
    generate_sample_data(tmp_path, SampleDataConfig(days=2, seed=41))
    battery_config = load_battery_config(tmp_path / "sample_battery_config.csv")
    health = calculate_battery_health(pd.read_csv(tmp_path / "sample_bess_telemetry.csv"), battery_config)
    degradation = calculate_degradation_cost(health, dict(battery_config), dispatch_revenue=0.0)

    report = compare_dispatch_strategies(
        site_load=pd.read_csv(tmp_path / "sample_site_load.csv"),
        pv_generation=pd.read_csv(tmp_path / "sample_pv_generation.csv"),
        tariff=pd.read_csv(tmp_path / "sample_tariff.csv"),
        battery_config=battery_config,
        degradation_stress_multiplier=degradation.stress_multiplier,
    )

    assert report.baseline.strategy == "no_battery"
    assert report.energy_cost_only.status == "optimal"
    assert report.degradation_aware.status == "optimal"
    assert report.energy_cost_only.gross_savings >= 0
    assert report.degradation_aware.gross_savings >= 0
    assert report.degradation_aware.degradation_cost >= 0
    assert report.baseline.peak_grid_import_kw > 0
    assert report.degradation_aware.peak_grid_import_kw >= 0
    assert "peak_grid_import_kw" in report.degradation_aware.to_dict()
    assert len(report.schedule) == 24


def test_degradation_aware_dispatch_uses_no_more_energy_than_cost_only_when_degradation_is_positive(tmp_path: Path) -> None:
    generate_sample_data(tmp_path, SampleDataConfig(days=2, seed=44))
    battery_config = load_battery_config(tmp_path / "sample_battery_config.csv")

    report = compare_dispatch_strategies(
        site_load=pd.read_csv(tmp_path / "sample_site_load.csv"),
        pv_generation=pd.read_csv(tmp_path / "sample_pv_generation.csv"),
        tariff=pd.read_csv(tmp_path / "sample_tariff.csv"),
        battery_config=battery_config,
        degradation_stress_multiplier=1.5,
    )

    assert report.degradation_aware.total_discharge_energy_kwh <= report.energy_cost_only.total_discharge_energy_kwh
