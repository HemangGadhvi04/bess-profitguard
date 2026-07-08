from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.app.services.battery_health import calculate_battery_health
from backend.app.services.degradation_cost import calculate_degradation_cost
from backend.app.services.dispatch_optimizer import compare_dispatch_strategies
from backend.app.services.telemetry_validator import load_battery_config


if __name__ == "__main__":
    data_dir = Path("data")
    battery_config = load_battery_config(data_dir / "sample_battery_config.csv")
    telemetry = pd.read_csv(data_dir / "sample_bess_telemetry.csv")
    health = calculate_battery_health(telemetry, battery_config)
    degradation = calculate_degradation_cost(health, dict(battery_config), dispatch_revenue=0.0)
    report = compare_dispatch_strategies(
        site_load=pd.read_csv(data_dir / "sample_site_load.csv"),
        pv_generation=pd.read_csv(data_dir / "sample_pv_generation.csv"),
        tariff=pd.read_csv(data_dir / "sample_tariff.csv"),
        battery_config=battery_config,
        degradation_stress_multiplier=degradation.stress_multiplier,
    )
    payload = report.to_dict()
    payload["schedule"] = payload["schedule"][:8]
    print(json.dumps(payload, indent=2))
