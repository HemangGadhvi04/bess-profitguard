# Case Study: EV Depot with Solar + BESS

This case study shows the core BESS ProfitGuard value proposition: energy arbitrage alone can look attractive, but the better commercial decision is the strategy that maximizes net savings after battery degradation.

## Site Setup

- Site type: EV charging depot with solar PV and a behind-the-meter BESS
- Data horizon: 7 days of synthetic 15-minute telemetry
- Dispatch comparison window: 24 hours
- Battery: 500 kWh nameplate, 450 kWh usable
- Power limits: 250 kW charge and 250 kW discharge
- Operating window: 10% to 95% SoC, with 20% reserve SoC
- EV demand: 20 charging sessions per day in the generated sample
- Commercial question: should the BESS chase tariff savings, or preserve battery life when degradation cost is too high?

## Sample Result

| Strategy | Energy Cost | Gross Savings | Degradation Cost | Net Savings | Discharge Energy | Final SoC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| No battery | ₹60,542.19 | ₹0.00 | ₹0.00 | ₹0.00 | 0.00 kWh | n/a |
| Energy-cost-only dispatch | ₹46,191.27 | ₹14,350.92 | ₹1,107.86 | ₹13,243.06 | 399.11 kWh | 50.00% |
| Degradation-aware dispatch | ₹46,647.21 | ₹13,894.98 | ₹593.33 | ₹13,301.65 | 213.75 kWh | 50.00% |

## Interpretation

The energy-cost-only optimizer produces the lowest electricity bill and the highest gross savings. However, it cycles the battery harder. Once degradation cost is included, the extra arbitrage is not worth the additional lifetime damage.

The degradation-aware strategy discharges about 185 kWh less during the day, accepts a slightly higher energy bill, and still produces higher net savings after battery wear. This is the commercial point of the product: it does not just ask whether dispatch is profitable today; it asks whether dispatch is still profitable after battery lifetime cost.

## Buyer-Relevant Recommendation

For an EV depot operator, the recommended action is to use BESS ProfitGuard as a decision-support audit before deploying aggressive EMS schedules. The report can identify days, tariffs, and operating modes where the BESS should operate normally, operate cautiously, or preserve battery life.

This is not yet a live EMS controller. It is a paid audit/report wedge that can be reviewed by energy managers, EPCs, charging operators, and asset owners before moving toward pilot integration.
