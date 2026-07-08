from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.app.services.battery_health import calculate_battery_health
from backend.app.services.degradation_cost import calculate_degradation_cost
from backend.app.services.dispatch_optimizer import compare_dispatch_strategies
from backend.app.services.report_generator import build_project_report, write_html_report
from backend.app.services.telemetry_validator import load_battery_config, validate_generated_dataset


if __name__ == "__main__":
    data_dir = Path("data")
    output_path = Path("reports/bess_profitguard_report.html")
    battery_config = load_battery_config(data_dir / "sample_battery_config.csv")
    validation_reports = validate_generated_dataset(data_dir)
    telemetry = pd.read_csv(data_dir / "sample_bess_telemetry.csv")
    health = calculate_battery_health(telemetry, battery_config)
    degradation = calculate_degradation_cost(health, dict(battery_config), dispatch_revenue=7_500.0)
    dispatch = compare_dispatch_strategies(
        site_load=pd.read_csv(data_dir / "sample_site_load.csv"),
        pv_generation=pd.read_csv(data_dir / "sample_pv_generation.csv"),
        tariff=pd.read_csv(data_dir / "sample_tariff.csv"),
        battery_config=battery_config,
        degradation_stress_multiplier=degradation.stress_multiplier,
        ev_sessions=pd.read_csv(data_dir / "sample_ev_sessions.csv"),
    )
    dispatch_high = compare_dispatch_strategies(
        site_load=pd.read_csv(data_dir / "sample_site_load.csv"),
        pv_generation=pd.read_csv(data_dir / "sample_pv_generation.csv"),
        tariff=pd.read_csv(data_dir / "sample_tariff.csv"),
        battery_config=battery_config,
        degradation_stress_multiplier=degradation.stress_multiplier * 1.5,
        ev_sessions=pd.read_csv(data_dir / "sample_ev_sessions.csv"),
    )
    dispatch_low = compare_dispatch_strategies(
        site_load=pd.read_csv(data_dir / "sample_site_load.csv"),
        pv_generation=pd.read_csv(data_dir / "sample_pv_generation.csv"),
        tariff=pd.read_csv(data_dir / "sample_tariff.csv"),
        battery_config=battery_config,
        degradation_stress_multiplier=degradation.stress_multiplier * 0.5,
        ev_sessions=pd.read_csv(data_dir / "sample_ev_sessions.csv"),
    )
    sensitivity = [
        ("Base case", dispatch.degradation_aware.net_savings),
        ("High degradation cost (+50%)", dispatch_high.degradation_aware.net_savings),
        ("Low degradation cost (-50%)", dispatch_low.degradation_aware.net_savings),
    ]
    report = build_project_report(
        validation_reports,
        health,
        degradation,
        dispatch,
        battery_config=dict(battery_config),
        sensitivity_analysis=sensitivity,
    )
    written = write_html_report(report, output_path)
    print(f"Generated report: {written}")
