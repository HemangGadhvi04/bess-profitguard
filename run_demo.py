# BESS ProfitGuard EV Depot Demo Flow

from pathlib import Path

import pandas as pd

from backend.app.services.battery_health import calculate_battery_health
from backend.app.services.data_generator import SampleDataConfig, generate_sample_data
from backend.app.services.degradation_cost import calculate_degradation_cost
from backend.app.services.dispatch_optimizer import compare_dispatch_strategies
from backend.app.services.report_generator import build_project_report, write_html_report
from backend.app.services.telemetry_validator import load_battery_config, validate_generated_dataset


def money(value: float) -> str:
    return f"₹{value:,.2f}"


def main() -> None:
    data_dir = Path("data")
    report_path = Path("reports/bess_profitguard_report.html")

    files = generate_sample_data(data_dir, SampleDataConfig(days=7, seed=42))
    print("Generated sample EV depot data")

    validation_reports = validate_generated_dataset(data_dir)
    print("Validated data quality")

    battery_config = load_battery_config(files["sample_battery_config"])
    health_report = calculate_battery_health(pd.read_csv(files["sample_bess_telemetry"]), battery_config)
    print("Calculated battery health")

    degradation_report = calculate_degradation_cost(health_report, dict(battery_config), dispatch_revenue=7_500.0)
    print("Calculated degradation cost")
    
    site_load = pd.read_csv(files["sample_site_load"])
    pv_generation = pd.read_csv(files["sample_pv_generation"])
    tariff = pd.read_csv(files["sample_tariff"])
    ev_sessions = pd.read_csv(files["sample_ev_sessions"])

    dispatch_report = compare_dispatch_strategies(
        site_load=site_load,
        pv_generation=pv_generation,
        tariff=tariff,
        battery_config=battery_config,
        degradation_stress_multiplier=degradation_report.stress_multiplier,
        ev_sessions=ev_sessions,
    )
    print("Compared dispatch strategies")

    dispatch_high = compare_dispatch_strategies(
        site_load=site_load,
        pv_generation=pv_generation,
        tariff=tariff,
        battery_config=battery_config,
        degradation_stress_multiplier=degradation_report.stress_multiplier * 1.5,
        ev_sessions=ev_sessions,
    )
    dispatch_low = compare_dispatch_strategies(
        site_load=site_load,
        pv_generation=pv_generation,
        tariff=tariff,
        battery_config=battery_config,
        degradation_stress_multiplier=degradation_report.stress_multiplier * 0.5,
        ev_sessions=ev_sessions,
    )
    sensitivity = [
        ("Base case", dispatch_report.degradation_aware.net_savings),
        ("High degradation cost (+50%)", dispatch_high.degradation_aware.net_savings),
        ("Low degradation cost (-50%)", dispatch_low.degradation_aware.net_savings),
    ]

    report = build_project_report(
        validation_reports,
        health_report,
        degradation_report,
        dispatch_report,
        battery_config=dict(battery_config),
        sensitivity_analysis=sensitivity,
    )
    written = write_html_report(report, report_path)
    print("Generated audit report")

    print()
    print(f"Validation: {'PASS' if all(item.passed for item in validation_reports) else 'FAIL'}")
    print(f"No battery cost: {money(dispatch_report.baseline.energy_cost)}")
    print(f"Energy-cost-only net savings: {money(dispatch_report.energy_cost_only.net_savings)}")
    print(f"Degradation-aware net savings: {money(dispatch_report.degradation_aware.net_savings)}")
    print(f"Recommended strategy: {dispatch_report.recommendation}")
    print()
    print("Report generated:")
    print(written)


if __name__ == "__main__":
    main()
