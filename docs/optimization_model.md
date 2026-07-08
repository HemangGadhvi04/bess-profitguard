# Dispatch Optimization Model

The BESS ProfitGuard uses a Linear Programming (LP) model implemented in `backend/app/services/dispatch_optimizer.py` to optimize battery dispatch.

## Objective
Maximize net financial savings over the defined horizon (typically 24 hours), which is equivalent to minimizing the total cost of grid energy imports minus solar exports and (if applicable) battery degradation.

## Decision Variables
For each time step in the horizon:
- `charge_kw`: Power charged into the battery.
- `discharge_kw`: Power discharged from the battery.
- `soc_kwh`: State of Charge (energy stored) in the battery.
- `grid_import_kw`: Power imported from the grid.
- `pv_export_kw`: Power exported to the grid.
- `ev_charge_kw`: EV charging power allocated to active charging sessions.
- `peak_import_kw`: Maximum grid import used for demand-charge modeling.
- `unmet_ev_energy_kwh`: Slack variable for infeasible EV charging demand, penalized heavily.

## Constraints
1. **Power Balance**: `grid_import_kw - pv_export_kw - charge_kw + discharge_kw - ev_charge_kw = site_load_kw - pv_generation_kw`
2. **State of Charge (SoC)**: `soc[t] = soc[t-1] + charge[t] * charge_efficiency - discharge[t] / discharge_efficiency`
3. **Power Limits**: 
   - `0 <= charge_kw <= max_charge_power_kw`
   - `0 <= discharge_kw <= max_discharge_power_kw`
4. **Energy Limits**: `min_energy_kwh <= soc_kwh <= max_energy_kwh`
5. **Terminal Constraint**: `soc[final] = terminal_energy_kwh` (for fair daily comparison).
6. **Grid/Export Limits**: Non-negative grid import and PV export.
7. **Demand Charge Peak**: `grid_import_kw[t] <= peak_import_kw`
8. **EV Session Windows**: EV charging is allowed only between each session arrival and departure.
9. **EV Energy Delivery**: EV charged energy plus unmet-energy slack must equal required session energy.

## Assumptions
- Perfect foresight of load, PV generation, and tariffs over the optimization horizon.
- Perfect foresight of EV arrivals, departures, required energy, and charger power limits.
- Constant charge and discharge efficiencies.
- Linear degradation cost per discharged kWh (for the degradation-aware strategy).
- Demand charge is modeled with the mean demand-charge value over the dispatch horizon.

## Limitations
- Linear programming requires linear relationships, so non-linear battery dynamics (e.g., efficiency varying with C-rate or SoC) are approximated or ignored.
- The model uses perfect forecasts, which may overestimate savings compared to real-world performance with forecast errors.
- Sub-hourly peaks are not fully captured if the data frequency is too coarse.
- EV unmet-energy slack is a feasibility guard, not a customer-service policy. Production use should expose unmet energy as a service-level risk.
