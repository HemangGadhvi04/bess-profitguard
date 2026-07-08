from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SampleDataConfig:
    start: str = "2026-01-05 00:00:00"
    days: int = 7
    freq: str = "15min"
    seed: int = 42
    battery_capacity_kwh: float = 500.0
    usable_capacity_kwh: float = 450.0
    max_charge_power_kw: float = 250.0
    max_discharge_power_kw: float = 250.0
    min_soc_percent: float = 10.0
    max_soc_percent: float = 95.0
    reserve_soc_percent: float = 20.0
    replacement_cost: float = 4_000_000.0
    expected_cycle_life: float = 5_000.0
    chemistry: str = "LFP"


def build_time_index(config: SampleDataConfig) -> pd.DatetimeIndex:
    periods_per_day = int(pd.Timedelta(days=1) / pd.Timedelta(config.freq))
    periods = config.days * periods_per_day
    return pd.date_range(config.start, periods=periods, freq=config.freq)


def generate_site_load(index: pd.DatetimeIndex, rng: np.random.Generator) -> pd.DataFrame:
    hours = (index.hour + index.minute / 60).to_numpy()
    weekday_factor = np.where(index.dayofweek < 5, 1.0, 0.82)
    morning = 75 * np.exp(-0.5 * ((hours - 10) / 3.0) ** 2)
    evening = 120 * np.exp(-0.5 * ((hours - 19) / 3.2) ** 2)
    base = 95 + morning + evening
    noise = rng.normal(0, 8, len(index))
    site_load = np.maximum(45, (base + noise) * weekday_factor)
    critical_load = np.maximum(25, site_load * 0.35)
    return pd.DataFrame(
        {
            "timestamp": index,
            "site_load_kw": site_load.round(3),
            "critical_load_kw": critical_load.round(3),
        }
    )


def generate_pv(index: pd.DatetimeIndex, rng: np.random.Generator) -> pd.DataFrame:
    hours = np.asarray(index.hour + index.minute / 60)
    daylight_shape = np.sin(np.pi * (hours - 6) / 12)
    daylight_shape = np.clip(daylight_shape, 0, None)
    daily_cloud_factor = pd.Series(index.date).astype("category").cat.codes.to_numpy()
    cloud_by_day = rng.uniform(0.72, 1.0, daily_cloud_factor.max() + 1)
    cloud = cloud_by_day[daily_cloud_factor]
    pv_kw = 320 * daylight_shape * cloud + rng.normal(0, 5, len(index))
    pv_kw = np.clip(pv_kw, 0, None)
    return pd.DataFrame({"timestamp": index, "pv_generation_kw": pv_kw.round(3)})


def generate_tariff(index: pd.DatetimeIndex) -> pd.DataFrame:
    hours = np.asarray(index.hour + index.minute / 60)
    price = np.select(
        [hours < 6, (hours >= 17) & (hours < 22)],
        [5.0, 14.0],
        default=8.0,
    )
    demand_charge = np.where((hours >= 17) & (hours < 22), 450.0, 0.0)
    export_price = np.full(len(index), 3.0)
    return pd.DataFrame(
        {
            "timestamp": index,
            "energy_price_per_kwh": price.round(3),
            "demand_charge_per_kw": demand_charge.round(3),
            "export_price_per_kwh": export_price.round(3),
        }
    )


def generate_ev_sessions(index: pd.DatetimeIndex, rng: np.random.Generator) -> pd.DataFrame:
    sessions: list[dict[str, object]] = []
    session_id = 1
    for day in pd.date_range(index.min().normalize(), periods=7, freq="D"):
        for _ in range(20):
            arrival_hour = rng.choice([7, 8, 9, 17, 18, 19], p=[0.08, 0.1, 0.12, 0.25, 0.25, 0.2])
            dwell_hours = int(rng.integers(3, 12))
            arrival = day + pd.Timedelta(hours=int(arrival_hour), minutes=int(rng.choice([0, 15, 30, 45])))
            departure = arrival + pd.Timedelta(hours=dwell_hours)
            sessions.append(
                {
                    "session_id": f"EV-{session_id:04d}",
                    "arrival_time": arrival,
                    "departure_time": departure,
                    "required_energy_kwh": round(float(rng.uniform(18, 75)), 3),
                    "max_charging_power_kw": float(rng.choice([7.2, 11.0, 22.0, 50.0])),
                    "priority_level": int(rng.choice([1, 2, 3], p=[0.2, 0.55, 0.25])),
                }
            )
            session_id += 1
    return pd.DataFrame(sessions)


def generate_battery_telemetry(
    index: pd.DatetimeIndex,
    pv: pd.DataFrame,
    load: pd.DataFrame,
    config: SampleDataConfig,
    rng: np.random.Generator,
) -> pd.DataFrame:
    pv_kw = pv["pv_generation_kw"].to_numpy()
    load_kw = load["site_load_kw"].to_numpy()
    hours = np.asarray(index.hour + index.minute / 60)
    dt_hours = pd.Timedelta(config.freq) / pd.Timedelta(hours=1)

    power = np.zeros(len(index))
    solar_surplus = pv_kw - load_kw
    power[(hours >= 10) & (hours < 15) & (solar_surplus > 35)] = -np.minimum(
        config.max_charge_power_kw * 0.72,
        solar_surplus[(hours >= 10) & (hours < 15) & (solar_surplus > 35)],
    )
    evening_peak = (hours >= 18) & (hours < 21)
    power[evening_peak] = np.minimum(config.max_discharge_power_kw * 0.78, load_kw[evening_peak] * 0.55)
    stress_window = np.asarray(index.dayofweek == 2) & (hours >= 19) & (hours < 20.5)
    power[stress_window] = config.max_discharge_power_kw * 0.98
    power += rng.normal(0, 2.5, len(index))
    power = np.clip(power, -config.max_charge_power_kw, config.max_discharge_power_kw)

    soc = np.zeros(len(index))
    soc[0] = 54.0
    for i in range(1, len(index)):
        previous_energy = soc[i - 1] / 100 * config.battery_capacity_kwh
        energy_delta = -power[i - 1] * dt_hours
        next_energy = previous_energy + energy_delta
        next_soc = next_energy / config.battery_capacity_kwh * 100
        soc[i] = np.clip(next_soc, config.min_soc_percent, config.max_soc_percent)

    daylight_heat = np.clip(np.sin(np.pi * (hours - 8) / 12), 0, None)
    temperature = 27 + 5 * daylight_heat + np.maximum(power, 0) * 0.018
    temperature += rng.normal(0, 1.1, len(index))
    temperature[stress_window] += 6.0
    voltage = 720 + (soc - 50) * 1.2 + rng.normal(0, 3.0, len(index))
    current = np.where(voltage > 0, power * 1000 / voltage, 0)

    return pd.DataFrame(
        {
            "timestamp": index,
            "battery_voltage_v": voltage.round(3),
            "battery_current_a": current.round(3),
            "battery_power_kw": power.round(3),
            "soc_percent": soc.round(3),
            "temperature_c": temperature.round(3),
        }
    )


def generate_battery_config(config: SampleDataConfig) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "battery_capacity_kwh": config.battery_capacity_kwh,
                "usable_capacity_kwh": config.usable_capacity_kwh,
                "max_charge_power_kw": config.max_charge_power_kw,
                "max_discharge_power_kw": config.max_discharge_power_kw,
                "min_soc_percent": config.min_soc_percent,
                "max_soc_percent": config.max_soc_percent,
                "reserve_soc_percent": config.reserve_soc_percent,
                "replacement_cost": config.replacement_cost,
                "expected_cycle_life": config.expected_cycle_life,
                "chemistry": config.chemistry,
            }
        ]
    )


def generate_sample_data(output_dir: Path | str = "data", config: SampleDataConfig | None = None) -> dict[str, Path]:
    config = config or SampleDataConfig()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(config.seed)
    index = build_time_index(config)

    load = generate_site_load(index, rng)
    pv = generate_pv(index, rng)
    tariff = generate_tariff(index)
    ev_sessions = generate_ev_sessions(index, rng)
    bess = generate_battery_telemetry(index, pv, load, config, rng)
    battery_config = generate_battery_config(config)

    datasets = {
        "sample_site_load": load,
        "sample_pv_generation": pv,
        "sample_tariff": tariff,
        "sample_ev_sessions": ev_sessions,
        "sample_bess_telemetry": bess,
        "sample_battery_config": battery_config,
    }
    written: dict[str, Path] = {}
    for name, frame in datasets.items():
        path = output_path / f"{name}.csv"
        frame.to_csv(path, index=False)
        written[name] = path
    return written
