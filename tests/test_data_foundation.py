from pathlib import Path

import pandas as pd

from backend.app.services.data_generator import SampleDataConfig, generate_sample_data
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
