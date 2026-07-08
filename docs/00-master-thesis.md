# Master Thesis

## Core Identity

The goal is to build an energy infrastructure software company.

The strongest direction is:

> Battery-aware grid-edge intelligence for renewable-heavy power systems.

Future grids will depend on batteries, inverters, EV chargers, microgrids, and distributed assets. The missing software layer is intelligence that understands both asset health and grid behavior.

## What This Is Not

This is not a plan to become:

- A generic solar installation person
- A solar panel sales or basic PV manufacturing-only professional
- A simple dashboard developer
- A pure AI/ML person without engineering depth
- An energy generation company founder
- Someone who optimizes electricity bills while ignoring hardware degradation

APS is a stepping stone, not the final destination.

## Main Thesis

Every energy decision has a hidden engineering cost. Batteries degrade, inverters trip, transformers overload, protection systems misoperate, and grids become unstable.

The opportunity is to build software that converts raw electrical telemetry into financial, operational, and reliability decisions.

The spine:

> Battery health -> degradation cost -> EMS optimization -> microgrid control -> inverter/grid diagnostics -> grid stability intelligence

## Market Pain

Choose problems where companies lose:

- Money
- Battery lifetime
- Uptime
- Safety
- Warranty value
- Operational reliability
- Commissioning time
- Grid stability

The moat is not the dashboard. The moat is the engineering intelligence behind the dashboard.

## Platform Layers

### Layer 1: Battery Health API

Purpose: understand the real health, risk, and remaining value of a battery.

Capabilities:

- BMS data ingestion
- SoC and SoH estimation
- Internal resistance tracking
- Capacity fade estimation
- Cycle counting
- Temperature stress analysis
- Remaining useful life prediction
- Second-life suitability score
- Warranty risk score

### Layer 2: Degradation Cost Engine

Purpose: convert battery aging into money.

Core question:

> If I discharge this battery today, how much revenue do I earn and how much lifetime value do I destroy?

Outputs:

- Degradation cost per cycle
- Calendar aging cost
- Cycle aging cost
- High-temperature, high-SoC, and high-C-rate penalties
- Lifetime value loss
- Warranty risk
- Asset depreciation estimate

### Layer 3: Degradation-Aware EMS

Purpose: decide when to charge, discharge, preserve, or reserve the battery.

Generic EMS says: discharge because tariff is high.

The target EMS says: discharge because tariff savings exceed degradation cost and operational reserve remains safe.

### Layer 4: Grid-Edge EMS

Purpose: coordinate solar, BESS, EV chargers, buildings, and grid import/export at site level.

Target sites:

- EV charging depots
- Commercial buildings
- Factories
- Campuses
- Industrial parks
- Localized microgrids
- Residential energy communities

### Layer 5: Inverter Event Forensics

Purpose: diagnose why inverters and BESS assets misbehave.

Capabilities:

- Trip analysis
- Waveform event detection
- FFT and THD analysis
- Harmonic detection
- Voltage sag/swell detection
- Frequency deviation analysis
- Sequence-of-events reconstruction
- Commissioning diagnostics

### Layer 6: Grid Stability Intelligence

Purpose: support renewable-heavy grids with stability, protection, and inverter-based resource intelligence.

Relevant domains:

- Grid-forming inverters
- Synthetic inertia
- Black start
- PMU/WAMS analytics
- Inverter-dominated protection
- Oscillation detection
- Grid-code compliance
- Digital twins
- Adaptive protection

## Domain Ranking

| Rank | Domain | Why It Matters | When to Focus |
| --- | --- | --- | --- |
| 1 | BESS diagnostics / battery health | Direct market pain, software-heavy, strong IP potential | Start early |
| 2 | Degradation-aware EMS | Turns analytics into control and revenue decisions | After battery foundation |
| 3 | PV reliability analytics at APS | Approachable industrial project and CV booster | Current internship |
| 4 | Second-life battery diagnostics | Strong future market, linked to BESS health | Medium-term |
| 5 | Inverter event forensics | Deep technical moat, strong industrial pain | Later with lab/data access |
| 6 | Grid-forming inverter control | Important, high difficulty | Germany/master's/research |
| 7 | HVDC / FACTS / SST hardware | Huge but capital-heavy and less approachable early | Long-term awareness |

## Career Narrative

I started with PV manufacturing reliability during my APS internship, where I studied EL imaging, microcracks, and module degradation. I used that experience to build skills in industrial reliability, computer vision, and statistical modeling. Then I moved deeper into BESS diagnostics, battery degradation modeling, and grid-edge optimization. My long-term goal is to build battery-aware energy infrastructure software for BESS owners, EV depots, microgrids, and renewable-heavy grids.

