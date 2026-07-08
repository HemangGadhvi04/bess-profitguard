from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backend.app.services.battery_health import calculate_battery_health
from backend.app.services.telemetry_validator import load_battery_config


if __name__ == "__main__":
    data_dir = Path("data")
    telemetry = pd.read_csv(data_dir / "sample_bess_telemetry.csv")
    battery_config = load_battery_config(data_dir / "sample_battery_config.csv")
    report = calculate_battery_health(telemetry, battery_config)
    print(json.dumps(report.to_dict(), indent=2))
