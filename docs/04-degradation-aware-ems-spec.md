# Degradation-Aware EMS Spec

## Vision

Move from energy monitoring to autonomous optimization.

Core question:

> Should this battery operate right now, or should it preserve lifetime?

## Inputs

- Load forecast
- PV forecast
- Tariff data
- Demand charge rules
- Battery SoH
- Battery temperature
- EV departure times
- Backup reserve requirement
- Transformer/site constraints

## Objectives

Optimize:

1. Electricity cost
2. Degradation cost
3. Operational readiness
4. Grid constraint compliance
5. Backup reserve

## Decision Logic

The simulator should compare:

- Revenue or savings from dispatch
- Estimated battery degradation cost
- Reserve violation risk
- Site constraint violation risk

Example output:

```txt
Peak shaving benefit: INR 8,000
Estimated degradation cost: INR 2,300
Net benefit: INR 5,700
Recommendation: Dispatch
```

## Recommended Stack

- Python
- pandas
- SciPy optimize or Pyomo
- PuLP for early linear optimization
- FastAPI
- PostgreSQL or TimescaleDB later
- React later, after the optimization logic works

## First Use Cases

- EV charging depot
- Commercial building
- Solar + BESS site
- Microgrid

## MVP Scope

The first simulator should:

- Accept 24-hour load, PV, tariff, and battery data
- Optimize charge/discharge schedule
- Include a simple degradation cost term
- Enforce SoC limits and reserve requirements
- Output net savings, degradation cost, and schedule

## Later Scope

- Demand charge optimization
- Multi-day lookahead
- EV departure constraints
- Transformer loading constraints
- Degradation model calibration from real telemetry
- Site-level control integration
- Edge/cloud deployment

