# Product Tracks and Commercial Plan

This repository uses two separate product tracks. They may share proven analytical
logic, but they must not be presented as the same product.

## A01 — BESS ProfitGuard

### Product definition

> A battery dispatch audit and optimization product that determines whether a
> BESS, solar+BESS, or EV-depot battery is genuinely profitable after degradation,
> demand charges, reserve requirements, and operational constraints are counted.

### First commercial offer

The first sellable offer is a **BESS Dispatch Audit**, not automatic control or a
full enterprise SaaS platform.

Customer inputs:

- Site load and tariff data
- Battery configuration
- BESS telemetry, when available
- Solar generation, when applicable
- EV sessions, when applicable

Customer deliverables:

1. Executive recommendation
2. Data-quality and confidence scores
3. Battery-health and stress summary
4. Peak-demand analysis
5. EV-readiness analysis, when applicable
6. Degradation-cost estimate
7. No-battery, naive, and degradation-aware strategy comparison
8. Monthly net-savings estimate
9. Recommended operating policy
10. Assumptions, sensitivity, and limitations

### Initial customers

Prioritize customers with relatively fast decision cycles:

1. Solar and BESS EPCs
2. EV charging and fleet-depot operators
3. Commercial and industrial sites
4. BESS operations and maintenance providers

### Commercial workflow

```text
Choose site type
→ Upload operational data
→ Review and edit assumptions
→ Run analysis
→ Receive a decision-first recommendation
→ Export the audit report
→ Repeat monthly when useful
```

### Required near-term improvements

- Editable assumptions panel
- Broader sensitivity analysis
- Clear dispatch/no-dispatch decision card
- Saved projects and report history
- Monthly billing-period analysis
- Professional PDF export
- Public case study
- Pilot-audit landing page and contact workflow

### Positioning

Headline:

> Maximize BESS savings without destroying battery lifetime.

Product promise:

> ProfitGuard compares normal battery dispatch with degradation-aware dispatch
> and shows whether the site is actually saving money after battery lifetime
> damage is counted.

### Commercial validation

Pricing is a hypothesis to test, not a proven claim. Early experiments may include:

| Offer | Indicative test range |
| --- | ---: |
| One-time site audit | ₹10,000–₹50,000 |
| Monthly site report | ₹5,000–₹30,000/month |
| EPC proposal tool | Setup fee plus monthly plan |
| Custom portfolio analysis | Quoted per project |

Success should be measured by real customer evidence:

- Qualified customer conversations
- Real or representative datasets received
- Audits delivered
- Recommendations accepted or challenged
- Demonstrated savings or avoided battery stress
- Repeat analysis requests
- Paid conversions

## A02 — DER Flexibility / VPP Readiness Platform

### Product definition

> A separate multi-site platform that estimates how much safe, profitable, and
> reliable flexibility a portfolio of distributed energy resources can offer.

A02 may reuse validated asset-level calculations from A01, but it owns the
portfolio data model, aggregation optimizer, grid-event simulation, and
portfolio reporting.

### First build

The first A02 release is a **Multi-Site Flexibility Simulator**, not a live VPP.

Initial asset scope:

- BESS charging and discharging flexibility
- Deferrable EV charging
- Site load and PV forecasts as contextual inputs

Initial outputs:

- Upward and downward flexibility
- Sustainable duration
- Activation and degradation cost
- EV-readiness risk
- Firm capacity after a reliability margin
- Flexibility supply curve
- Asset-selection explanation
- Simulated grid-event performance

### Long-term sequence

```text
Multi-site flexibility assessment
→ Portfolio aggregation and bid recommendation
→ Historical event backtesting
→ Read-only telemetry pilot
→ Dispatch approval workflow
→ Automated control and verification
→ Market integration and settlement
```

Do not describe A02 as a production VPP until it has real asset agreements,
telemetry, reliable controls, measurement and verification, cybersecurity,
regulatory access, and settlement capability.

## Boundary Between A01 and A02

| Area | A01 | A02 |
| --- | --- | --- |
| Primary unit | One site | Portfolio of sites |
| Main buyer | EPC, operator, C&I site, O&M provider | Aggregator, utility pilot, multi-site operator |
| Main decision | Should this battery dispatch? | Which assets should provide flexibility? |
| First revenue | Audit/report | Flexibility assessment/pilot |
| Control scope | Decision support | Simulation first; control much later |
| Core value | Net value after degradation | Firm portfolio flexibility after constraints |

Each track must maintain its own roadmap, product positioning, interfaces,
datasets, reports, and release versions.

## 90-Day Commercial Focus for A01

### Days 1–30: Commercial audit quality

- Verify the complete demo pipeline and tests
- Add editable assumptions to the dashboard
- Expand scenario sensitivity
- Improve the decision card and report design
- Produce a polished public EV-depot case study

### Days 31–45: Pilot workflow

- Make uploads and validation customer-friendly
- Add saved audit/report history
- Add professional PDF export
- Publish a pilot-audit request page

### Days 46–60: Customer discovery

- Contact solar/BESS EPCs
- Contact EV charging operators
- Contact battery and inverter partners
- Contact energy consultants
- Seek two qualified conversations and one usable dataset

### Days 61–90: Pilot evidence

- Complete one real or representative pilot audit
- Record assumptions, objections, and recommendation changes
- Validate results with the customer where possible
- Publish an anonymized case study with permission
- Test a paid second engagement

## Explicitly Deferred

Unless required by a signed pilot, defer:

- Automatic hardware control
- Electricity-market bidding
- Settlement
- Full VPP orchestration
- Production Modbus/OCPP integrations
- Kafka-scale infrastructure
- Reinforcement learning
- Safety-critical dispatch

The near-term commercial loop is:

> Audit → recommendation → report → customer feedback → monthly monitoring.
