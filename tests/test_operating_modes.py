import pytest

from backend.app.services.operating_modes import get_operating_mode


def test_operating_modes_have_expected_penalty_shape() -> None:
    profit = get_operating_mode("profit_mode")
    protection = get_operating_mode("battery_protection_mode")
    readiness = get_operating_mode("ev_readiness_mode")

    assert protection.degradation_penalty_multiplier > profit.degradation_penalty_multiplier
    assert readiness.ev_unmet_penalty_per_kwh > profit.ev_unmet_penalty_per_kwh


def test_unknown_operating_mode_is_rejected() -> None:
    with pytest.raises(ValueError):
        get_operating_mode("unknown_mode")
