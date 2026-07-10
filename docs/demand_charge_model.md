# Demand Charge Model

BESS ProfitGuard models demand charges because many commercial and industrial sites pay for their highest grid-import peak, not only total energy consumption.

## Metrics

- `peak_grid_import_kw`: highest modeled grid import during the dispatch horizon
- `demand_charge_cost`: `peak_grid_import_kw * demand_charge_rate_per_kw`
- `peak_shaving_savings`: baseline demand charge minus optimized demand charge
- `monthly_peak_shaving_savings`: daily modeled savings projected across 30 days

## Optimization Role

The dispatch optimizer includes demand charge cost directly in the linear-program objective:

```txt
energy_import_cost - export_revenue + demand_charge_cost + degradation_cost + unmet_ev_penalty
```

This makes the optimizer useful for EV depots, factories, malls, hospitals, and other sites where shaving peak import can be more valuable than simple time-of-use arbitrage.

## Limitation

The current model uses the mean demand-charge rate across the 24-hour dispatch horizon. Production tariff modeling should support monthly billing windows, ratchets, seasonal charges, and utility-specific rules.
