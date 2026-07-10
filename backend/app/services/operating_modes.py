from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OperatingModeConfig:
    name: str
    label: str
    degradation_penalty_multiplier: float
    ev_unmet_penalty_per_kwh: float
    description: str

    def to_dict(self) -> dict[str, float | str]:
        return {
            "name": self.name,
            "label": self.label,
            "degradation_penalty_multiplier": self.degradation_penalty_multiplier,
            "ev_unmet_penalty_per_kwh": self.ev_unmet_penalty_per_kwh,
            "description": self.description,
        }


OPERATING_MODES: dict[str, OperatingModeConfig] = {
    "profit_mode": OperatingModeConfig(
        name="profit_mode",
        label="Profit Mode",
        degradation_penalty_multiplier=1.0,
        ev_unmet_penalty_per_kwh=1_000.0,
        description="Maximize net savings while accounting for degradation and EV deadlines.",
    ),
    "battery_protection_mode": OperatingModeConfig(
        name="battery_protection_mode",
        label="Battery Protection Mode",
        degradation_penalty_multiplier=1.6,
        ev_unmet_penalty_per_kwh=1_000.0,
        description="Increase the degradation penalty to protect older, hotter, or warranty-sensitive batteries.",
    ),
    "ev_readiness_mode": OperatingModeConfig(
        name="ev_readiness_mode",
        label="EV Readiness Mode",
        degradation_penalty_multiplier=1.0,
        ev_unmet_penalty_per_kwh=5_000.0,
        description="Prioritize EV departure readiness when fleet service reliability matters most.",
    ),
}


def get_operating_mode(name: str | None) -> OperatingModeConfig:
    mode_name = name or "profit_mode"
    if mode_name not in OPERATING_MODES:
        allowed = ", ".join(sorted(OPERATING_MODES))
        raise ValueError(f"Unsupported operating_mode '{mode_name}'. Allowed modes: {allowed}")
    return OPERATING_MODES[mode_name]
