# Degradation Cost Model

The degradation cost model is implemented in `backend/app/services/degradation_cost.py` and estimates the financial impact of battery usage.

## Components

1. **Base cycle cost**: Calculated as `replacement_cost / expected_cycle_life`. This provides a baseline cost per equivalent full cycle (EFC).
2. **Stress multiplier**: An aggregate multiplier (capped at a maximum value) that scales the base cycle cost based on operational stress factors.
3. **Temperature multiplier**: Increases degradation cost if the battery operates at high temperatures for extended periods.
4. **SoC dwell multiplier**: Increases degradation cost if the battery spends significant time at extreme (high or low) State of Charge levels.
5. **C-rate multiplier**: Increases degradation cost for high charge/discharge rates compared to a reference C-rate.
6. **SoH multiplier**: Increases degradation cost as the battery's State of Health (SoH) declines, reflecting accelerated aging near end-of-life.

## Decision-Support Estimate
This model provides a **decision-support estimate**, not a physics-based or OEM-certified prediction. It aims to translate operational stress into a financial penalty to guide dispatch decisions. By assigning a cost to damaging behaviors, the optimizer can avoid them if the energy arbitrage revenue doesn't justify the battery wear.
