from backend.app.services.demand_charge import calculate_demand_charge_cost, compare_demand_charge


def test_demand_charge_calculation_is_peak_times_rate() -> None:
    assert calculate_demand_charge_cost(510.0, 450.0) == 229_500.0


def test_peak_shaving_savings_are_reported() -> None:
    metrics = compare_demand_charge(
        baseline_peak_grid_import_kw=620.0,
        optimized_peak_grid_import_kw=505.0,
        demand_charge_rate_per_kw=450.0,
    )

    assert metrics.peak_shaving_kw == 115.0
    assert metrics.peak_shaving_savings == 51_750.0
    assert metrics.monthly_peak_shaving_savings == 1_552_500.0
