from pathlib import Path

import pandas as pd

from backend.app.services.battery_health import calculate_battery_health
from backend.app.services.data_generator import SampleDataConfig, generate_sample_data
from backend.app.services.degradation_cost import calculate_degradation_cost
from backend.app.services.dispatch_optimizer import compare_dispatch_strategies
from backend.app.services.report_generator import build_project_report, render_html_report, write_html_report
from backend.app.services.telemetry_validator import load_battery_config, validate_generated_dataset


def test_report_generator_renders_core_sections(tmp_path: Path) -> None:
    generate_sample_data(tmp_path, SampleDataConfig(days=2, seed=51))
    battery_config = load_battery_config(tmp_path / "sample_battery_config.csv")
    validation_reports = validate_generated_dataset(tmp_path)
    health = calculate_battery_health(pd.read_csv(tmp_path / "sample_bess_telemetry.csv"), battery_config)
    degradation = calculate_degradation_cost(health, dict(battery_config), dispatch_revenue=7500.0)
    dispatch = compare_dispatch_strategies(
        site_load=pd.read_csv(tmp_path / "sample_site_load.csv"),
        pv_generation=pd.read_csv(tmp_path / "sample_pv_generation.csv"),
        tariff=pd.read_csv(tmp_path / "sample_tariff.csv"),
        battery_config=battery_config,
        degradation_stress_multiplier=degradation.stress_multiplier,
    )

    report = build_project_report(validation_reports, health, degradation, dispatch, battery_config=dict(battery_config))
    html = render_html_report(report)

    assert "BESS ProfitGuard Dispatch Audit" in html
    assert "Data Validation" in html
    assert "Battery Health" in html
    assert "Degradation Cost" in html
    assert "Dispatch Strategy Comparison" in html
    assert "Assumptions and Limitations" in html
    assert "Decision-support model, not OEM certification" in html
    assert "degradation_aware" in html


def test_report_generator_writes_html_file(tmp_path: Path) -> None:
    generate_sample_data(tmp_path, SampleDataConfig(days=2, seed=52))
    battery_config = load_battery_config(tmp_path / "sample_battery_config.csv")
    validation_reports = validate_generated_dataset(tmp_path)
    health = calculate_battery_health(pd.read_csv(tmp_path / "sample_bess_telemetry.csv"), battery_config)
    degradation = calculate_degradation_cost(health, dict(battery_config), dispatch_revenue=7500.0)
    dispatch = compare_dispatch_strategies(
        site_load=pd.read_csv(tmp_path / "sample_site_load.csv"),
        pv_generation=pd.read_csv(tmp_path / "sample_pv_generation.csv"),
        tariff=pd.read_csv(tmp_path / "sample_tariff.csv"),
        battery_config=battery_config,
        degradation_stress_multiplier=degradation.stress_multiplier,
    )
    report = build_project_report(validation_reports, health, degradation, dispatch)

    output = write_html_report(report, tmp_path / "report.html")

    assert output.exists()
    assert output.read_text(encoding="utf-8").startswith("<!doctype html>")
