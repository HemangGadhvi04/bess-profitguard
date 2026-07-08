# Product Improvement Roadmap

## Improved Product Definition

> BESS ProfitGuard is a degradation-aware battery dispatch decision platform for BESS-supported EV charging depots and commercial microgrids. It validates energy data, estimates battery stress and degradation cost, compares naive dispatch against degradation-aware dispatch, and generates an operating schedule that maximizes net financial value while preserving battery lifetime.

The core product answer should be:

| Question | Product Answer |
| --- | --- |
| Should I discharge now? | Yes / No |
| Why? | Net profit after degradation |
| How much will I earn? | Savings / revenue |
| How much battery life will I lose? | Degradation cost |
| What is the safer schedule? | Optimized dispatch |
| What risk am I creating? | Temperature, SoC, warranty, reserve, EV readiness |

## Current MVP Status

| Capability | Status |
| --- | --- |
| Synthetic data generator | Done |
| CSV validator | Done |
| Battery health summary | Done |
| Degradation cost engine | Done |
| 24-hour dispatch optimizer | Done |
| No-battery baseline | Done |
| Naive versus degradation-aware comparison | Done |
| HTML audit report | Done |
| FastAPI backend | Done |
| Upload/session flow | Done |
| Lightweight dashboard | Done |
| Dashboard charts | Done |
| Security hardening | Started |

## P0: Flagship Foundation

These are the must-have features for the project to be credible.

1. Synthetic data generator
2. CSV validator
3. Battery health summary
4. Degradation cost engine
5. 24-hour dispatch optimizer
6. Naive versus degradation-aware comparison
7. HTML report
8. Strong README

Most P0 items are already implemented.

## P1: Strong Differentiators

Build these next.

### 1. Battery Usefulness Decision Card

Main output:

```txt
Recommended Action: DISPATCH

Expected tariff savings: INR 12,400
Estimated degradation cost: INR 3,100
Net benefit: INR 9,300
Battery temperature: safe
Reserve SoC after dispatch: 32%
EV readiness: 100%

Decision:
Dispatch from 18:00 to 20:00 only.
Avoid discharge after 20:00 because degradation cost exceeds benefit.
```

### 2. Operating Modes

Add three modes:

- Profit Mode: maximize net savings.
- Battery Protection Mode: reduce cycling and protect lifetime.
- EV Readiness Mode: ensure EVs are charged before departure.

### 3. Transparent Assumptions Panel

Expose assumptions:

- battery replacement cost
- expected cycle life
- usable capacity
- base degradation cost
- high-temperature threshold
- high-SoC threshold
- reserve SoC
- round-trip efficiency

Users should be able to change these values later.

### 4. Sensitivity Analysis

Show how net benefit changes when key assumptions change:

- battery replacement cost
- cycle life
- tariff spread
- degradation multiplier

Example:

| Battery Replacement Cost | Net Benefit |
| --- | ---: |
| INR 30 lakh | INR 7,200 |
| INR 40 lakh | INR 5,300 |
| INR 50 lakh | INR 3,400 |
| INR 60 lakh | INR 1,500 |

### 5. Confidence Level

Add confidence output:

- High
- Medium
- Low

Example reasons:

- telemetry data quality is good
- temperature data is available
- manufacturer degradation curve is not available
- EV data is incomplete

### 6. Data Quality Score

Convert validation results into a score:

```txt
Data Quality Score: 82/100
```

Issue examples:

- missing timestamps
- duplicate records
- SoC jumps
- infeasible EV sessions
- missing temperature data

### 7. EV Charging Feasibility

Detect infeasible EV sessions:

```txt
EV 07 arrives at 22:00
Departs at 05:00
Required energy: 80 kWh
Max charger power: 7 kW

Required time: 11.4 hours
Available time: 7 hours
Status: Infeasible
```

Recommendations:

- increase charger power
- reduce required energy
- prioritize vehicle earlier
- add backup charging window

### 8. Warranty Risk Monitor

Flag:

- SoC above 95%
- SoC below 5%
- temperature above safe threshold
- high C-rate operation
- excessive daily cycles
- deep discharge
- reserve violation
- repeated high-temperature charging

Output:

```txt
Warranty Risk Events This Month: 14
High severity: 3
Medium severity: 8
Low severity: 3
```

### 9. Dispatch Explanation

Every recommendation should explain itself.

Bad:

> Discharge at 18:00.

Good:

> Discharge at 18:00 because tariff is high, site load is near peak, battery temperature is safe, reserve SoC remains above 30%, and estimated net benefit is positive.

### 10. Monthly Report

A 24-hour optimizer is useful for engineering. A monthly report is more useful commercially.

Add:

- monthly gross savings
- monthly degradation cost
- monthly net savings
- peak demand reduction
- EFC used
- battery stress events
- EV readiness score
- recommended policy changes

### 11. Case Study

Create one polished case study:

```txt
EV Depot with Solar + BESS
20 EVs
500 kWh BESS
300 kW solar
grid import limit
time-of-use tariff
EV departure deadlines
```

Outputs:

- naive dispatch versus degradation-aware dispatch
- savings comparison
- battery stress comparison
- EV readiness
- report export

### 12. Limitations Section

Add this language to reports and docs:

```txt
This tool provides decision-support estimates, not manufacturer-certified degradation predictions.
Results depend on input data quality and assumed battery parameters.
Real deployment requires validation with site-specific BMS data and OEM warranty conditions.
```

## P2: Advanced Germany / Research Features

Build later:

1. Rainflow counting
2. ECM / EKF battery state estimation
3. PyBaMM integration
4. 15-minute optimizer
5. stochastic load and EV arrival forecasting
6. Modbus / MQTT telemetry simulator
7. inverter event analytics

## Delay

Delay these until the core reporting product is proven:

- Kafka
- real-time control
- hardware integration
- reinforcement learning
- advanced deep learning
- complex cloud microservices
- blockchain / VPP market
- grid-forming inverter simulation

## Documentation Upgrades

Create:

```txt
docs/problem_statement.md
docs/data_schema.md
docs/degradation_model.md
docs/optimization_model.md
docs/assumptions.md
docs/case_study_ev_depot.md
docs/limitations.md
docs/germany_cv_summary.md
```

## GitHub README Upgrade

The README should eventually include:

1. Problem statement
2. Why degradation-aware dispatch matters
3. Product screenshot
4. Architecture diagram
5. Features
6. Sample inputs
7. Sample outputs
8. Baseline comparison
9. Tech stack
10. How to run
11. Future work
12. Resume bullets

