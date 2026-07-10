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

| Strategy | Energy Cost | Demand Charge | Gross Savings | Degradation Cost | Net Savings | EV Readiness | Peak Demand | Discharge Energy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| No battery | ₹49,754.66 | ₹25,274.91 | ₹0.00 | ₹0.00 | ₹0.00 | 100.00% | 269.60 kW | 0.00 kWh |
| Energy-cost-only dispatch | ₹39,474.74 | ₹18,084.80 | ₹10,279.92 | ₹1,113.27 | ₹9,166.65 | 100.00% | 192.91 kW | 401.06 kWh |
| Degradation-aware dispatch | ₹39,901.32 | ₹18,084.80 | ₹9,853.34 | ₹631.89 | ₹9,221.45 | 100.00% | 192.91 kW | 227.64 kWh |

## Interpretation

The energy-cost-only optimizer produces the lowest electricity bill and the highest gross savings. However, it cycles the battery harder. Once degradation cost is included, the extra arbitrage is not worth the additional lifetime damage.

The degradation-aware strategy discharges about 173 kWh less during the day, accepts a slightly higher energy bill, keeps EV readiness at 100%, and still produces higher net savings after battery wear. This is the commercial point of the product: it does not just ask whether dispatch is profitable today; it asks whether dispatch is still profitable after battery lifetime cost and depot readiness are counted.

## Buyer-Relevant Recommendation

For an EV depot operator, the recommended action is to use BESS ProfitGuard as a decision-support audit before deploying aggressive EMS schedules. The report can identify days, tariffs, and operating modes where the BESS should operate normally, operate cautiously, or preserve battery life.

This is not yet a live EMS controller. It is a paid audit/report wedge that can be reviewed by energy managers, EPCs, charging operators, and asset owners before moving toward pilot integration.
