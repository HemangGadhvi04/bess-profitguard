from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class ValidationIssue:
    severity: str
    code: str
    message: str
    count: int = 0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    dataset: str
    row_count: int
    issues: list[ValidationIssue]

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "warning")

    @property
    def passed(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "row_count": self.row_count,
            "passed": self.passed,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [
                {
                    "severity": issue.severity,
                    "code": issue.code,
                    "message": issue.message,
                    "count": issue.count,
                    "details": issue.details,
                }
                for issue in self.issues
            ],
        }


def _issue(severity: str, code: str, message: str, count: int = 0, **details: Any) -> ValidationIssue:
    return ValidationIssue(severity=severity, code=code, message=message, count=count, details=details)


def _require_columns(frame: pd.DataFrame, required: set[str], issues: list[ValidationIssue]) -> bool:
    missing = sorted(required - set(frame.columns))
    if missing:
        issues.append(_issue("error", "missing_columns", "Required columns are missing.", len(missing), columns=missing))
        return False
    return True


def _parse_timestamp(frame: pd.DataFrame, column: str, issues: list[ValidationIssue]) -> pd.Series:
    parsed = pd.to_datetime(frame[column], errors="coerce")
    invalid = int(parsed.isna().sum())
    if invalid:
        issues.append(_issue("error", "invalid_timestamp", f"{column} contains invalid timestamps.", invalid))
    return parsed


def _validate_regular_timeseries(
    frame: pd.DataFrame,
    timestamp: pd.Series,
    expected_freq: str,
    issues: list[ValidationIssue],
) -> None:
    duplicates = int(timestamp.duplicated().sum())
    if duplicates:
        issues.append(_issue("error", "duplicate_timestamps", "Duplicate timestamps detected.", duplicates))

    ordered = frame.assign(_timestamp=timestamp).dropna(subset=["_timestamp"]).sort_values("_timestamp")
    expected = pd.date_range(ordered["_timestamp"].min(), ordered["_timestamp"].max(), freq=expected_freq)
    missing = expected.difference(pd.DatetimeIndex(ordered["_timestamp"]))
    if len(missing):
        issues.append(
            _issue(
                "error",
                "missing_timestamps",
                "Missing timestamps detected in regular time series.",
                len(missing),
                first_missing=str(missing[0]),
            )
        )

    deltas = ordered["_timestamp"].diff().dropna()
    expected_delta = pd.Timedelta(expected_freq)
    irregular = int((deltas != expected_delta).sum())
    if irregular:
        issues.append(_issue("warning", "irregular_interval", "Irregular interval lengths detected.", irregular))


def validate_bess_telemetry(
    frame: pd.DataFrame,
    battery_config: pd.Series | dict[str, Any],
    expected_freq: str = "15min",
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    required = {
        "timestamp",
        "battery_voltage_v",
        "battery_current_a",
        "battery_power_kw",
        "soc_percent",
        "temperature_c",
    }
    if not _require_columns(frame, required, issues):
        return ValidationReport("bess_telemetry", len(frame), issues)

    timestamp = _parse_timestamp(frame, "timestamp", issues)
    if not timestamp.isna().all():
        _validate_regular_timeseries(frame, timestamp, expected_freq, issues)

    invalid_soc = int(((frame["soc_percent"] < 0) | (frame["soc_percent"] > 100)).sum())
    if invalid_soc:
        issues.append(_issue("error", "invalid_soc", "SoC must stay between 0 and 100 percent.", invalid_soc))

    temp_outliers = int(((frame["temperature_c"] < -20) | (frame["temperature_c"] > 70)).sum())
    if temp_outliers:
        issues.append(_issue("error", "invalid_temperature", "Temperature is outside expected operating bounds.", temp_outliers))

    voltage_outliers = int(((frame["battery_voltage_v"] <= 0) | (frame["battery_voltage_v"] > 1500)).sum())
    if voltage_outliers:
        issues.append(_issue("error", "invalid_voltage", "Battery voltage is outside expected bounds.", voltage_outliers))

    config = dict(battery_config)
    max_charge = float(config["max_charge_power_kw"])
    max_discharge = float(config["max_discharge_power_kw"])
    power_violations = int(((frame["battery_power_kw"] < -max_charge) | (frame["battery_power_kw"] > max_discharge)).sum())
    if power_violations:
        issues.append(_issue("error", "power_limit_violation", "Battery power exceeds configured inverter limits.", power_violations))

    high_temp = int((frame["temperature_c"] > 35).sum())
    if high_temp:
        issues.append(_issue("warning", "high_temperature_exposure", "Battery temperature exceeds 35 C.", high_temp))

    high_soc = int((frame["soc_percent"] > 85).sum())
    if high_soc:
        issues.append(_issue("warning", "high_soc_dwell", "Battery SoC exceeds 85 percent.", high_soc))

    return ValidationReport("bess_telemetry", len(frame), issues)


def validate_site_load(frame: pd.DataFrame, expected_freq: str = "15min") -> ValidationReport:
    issues: list[ValidationIssue] = []
    required = {"timestamp", "site_load_kw", "critical_load_kw"}
    if not _require_columns(frame, required, issues):
        return ValidationReport("site_load", len(frame), issues)
    timestamp = _parse_timestamp(frame, "timestamp", issues)
    _validate_regular_timeseries(frame, timestamp, expected_freq, issues)
    negative = int(((frame["site_load_kw"] < 0) | (frame["critical_load_kw"] < 0)).sum())
    if negative:
        issues.append(_issue("error", "negative_load", "Load values cannot be negative.", negative))
    excessive_critical = int((frame["critical_load_kw"] > frame["site_load_kw"]).sum())
    if excessive_critical:
        issues.append(_issue("warning", "critical_load_exceeds_site_load", "Critical load exceeds site load.", excessive_critical))
    return ValidationReport("site_load", len(frame), issues)


def validate_pv_generation(frame: pd.DataFrame, expected_freq: str = "15min") -> ValidationReport:
    issues: list[ValidationIssue] = []
    required = {"timestamp", "pv_generation_kw"}
    if not _require_columns(frame, required, issues):
        return ValidationReport("pv_generation", len(frame), issues)
    timestamp = _parse_timestamp(frame, "timestamp", issues)
    _validate_regular_timeseries(frame, timestamp, expected_freq, issues)
    negative = int((frame["pv_generation_kw"] < 0).sum())
    if negative:
        issues.append(_issue("error", "negative_pv", "PV generation cannot be negative.", negative))
    return ValidationReport("pv_generation", len(frame), issues)


def validate_tariff(frame: pd.DataFrame, expected_freq: str = "15min") -> ValidationReport:
    issues: list[ValidationIssue] = []
    required = {"timestamp", "energy_price_per_kwh", "demand_charge_per_kw", "export_price_per_kwh"}
    if not _require_columns(frame, required, issues):
        return ValidationReport("tariff", len(frame), issues)
    timestamp = _parse_timestamp(frame, "timestamp", issues)
    _validate_regular_timeseries(frame, timestamp, expected_freq, issues)
    negative = int(
        (
            (frame["energy_price_per_kwh"] < 0)
            | (frame["demand_charge_per_kw"] < 0)
            | (frame["export_price_per_kwh"] < 0)
        ).sum()
    )
    if negative:
        issues.append(_issue("error", "negative_tariff", "Tariff values cannot be negative.", negative))
    return ValidationReport("tariff", len(frame), issues)


def validate_ev_sessions(frame: pd.DataFrame) -> ValidationReport:
    issues: list[ValidationIssue] = []
    required = {"session_id", "arrival_time", "departure_time", "required_energy_kwh", "max_charging_power_kw", "priority_level"}
    if not _require_columns(frame, required, issues):
        return ValidationReport("ev_sessions", len(frame), issues)

    arrival = _parse_timestamp(frame, "arrival_time", issues)
    departure = _parse_timestamp(frame, "departure_time", issues)
    invalid_window = int((departure <= arrival).sum())
    if invalid_window:
        issues.append(_issue("error", "invalid_ev_window", "EV departure must be after arrival.", invalid_window))

    hours_available = (departure - arrival).dt.total_seconds() / 3600
    deliverable_energy = hours_available * frame["max_charging_power_kw"]
    impossible = int((frame["required_energy_kwh"] > deliverable_energy).sum())
    if impossible:
        issues.append(_issue("warning", "ev_energy_infeasible", "Required EV energy exceeds connection-window capability.", impossible))

    nonpositive = int(((frame["required_energy_kwh"] <= 0) | (frame["max_charging_power_kw"] <= 0)).sum())
    if nonpositive:
        issues.append(_issue("error", "nonpositive_ev_values", "EV energy and charging power must be positive.", nonpositive))
    return ValidationReport("ev_sessions", len(frame), issues)


def load_battery_config(path: Path | str) -> pd.Series:
    frame = pd.read_csv(path)
    if frame.empty:
        raise ValueError("Battery config CSV is empty.")
    return frame.iloc[0]


def validate_generated_dataset(data_dir: Path | str = "data", expected_freq: str = "15min") -> list[ValidationReport]:
    data_path = Path(data_dir)
    battery_config = load_battery_config(data_path / "sample_battery_config.csv")
    return [
        validate_bess_telemetry(pd.read_csv(data_path / "sample_bess_telemetry.csv"), battery_config, expected_freq),
        validate_site_load(pd.read_csv(data_path / "sample_site_load.csv"), expected_freq),
        validate_pv_generation(pd.read_csv(data_path / "sample_pv_generation.csv"), expected_freq),
        validate_tariff(pd.read_csv(data_path / "sample_tariff.csv"), expected_freq),
        validate_ev_sessions(pd.read_csv(data_path / "sample_ev_sessions.csv")),
    ]
