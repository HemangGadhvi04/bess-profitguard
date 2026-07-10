# Operating Modes

BESS ProfitGuard supports three operating modes to make the optimizer feel closer to real EMS software.

## Profit Mode

```txt
profit_mode
```

Default mode. Maximizes net savings after energy cost, demand charge, EV readiness penalty, and battery degradation cost.

## Battery Protection Mode

```txt
battery_protection_mode
```

Increases the degradation penalty. This is useful when the battery is hot, old, warranty-sensitive, or has low estimated SoH.

## EV Readiness Mode

```txt
ev_readiness_mode
```

Increases the penalty for unmet EV energy. This is useful for depots where vans, buses, or logistics vehicles must leave on time.

## API Usage

`POST /api/dispatch` and `POST /api/report` accept:

```json
{
  "data_dir": "data",
  "dispatch_revenue": 7500,
  "operating_mode": "profit_mode"
}
```

Allowed values:

- `profit_mode`
- `battery_protection_mode`
- `ev_readiness_mode`
