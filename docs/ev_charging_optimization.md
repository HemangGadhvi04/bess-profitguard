# EV Charging Optimization

BESS ProfitGuard treats EV charging demand as part of the optimizer, not only as data to validate.

## Decision Variable

```txt
ev_charge_power[t, ev]
```

For every EV session, the optimizer decides how much charging power to allocate at each timestep.

## Constraints

- EVs can charge only between `arrival_time` and `departure_time`.
- EV charging power cannot exceed `max_charging_power_kw`.
- Required energy must be delivered before departure unless the session is infeasible.
- Infeasible unmet energy is tracked as `unmet_ev_energy_kwh` and penalized heavily.

## Readiness Metrics

- `ev_readiness_percent`
- `priority_ev_readiness_percent`
- `unmet_ev_energy_kwh`

Priority EVs are identified by `priority_level <= 2`. This allows the report to show whether critical vehicles were protected before lower-priority charging.

## Limitation

The current optimizer reports aggregate EV charging in the public schedule. A production EV depot pilot should also expose per-vehicle charging timelines and charger-level occupancy.
