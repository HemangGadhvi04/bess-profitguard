# BESS ProfitGuard

Battery-aware EMS and BESS intelligence software for EV charging sites and commercial microgrids.

The core product question:

> Should the battery operate right now, or will the lifetime damage cost more than the money earned?

## Current Build

The first working milestone is the data foundation for a degradation-aware BESS/EV charging EMS:

1. Generate synthetic 7-day, 15-minute EV depot and BESS datasets.
2. Validate telemetry, tariff, PV, load, EV sessions, and battery config files.
3. Produce a data quality report with errors and operational warnings.
4. Calculate the first battery health report from BESS telemetry.
5. Convert battery cycling and stress into estimated degradation cost.
6. Compare no-battery, energy-cost-only, and degradation-aware dispatch strategies.
7. Generate a professional HTML dispatch audit report.
8. Expose the MVP pipeline through a FastAPI backend.
9. Support upload/session folders for user-provided CSV datasets.
10. Serve a lightweight dashboard for sample-data generation and analysis review.

This foundation supports the next modules:

1. Battery Health Engine
2. Degradation Cost Engine
3. Dispatch Optimization Engine
4. Financial and Risk Report Generator
5. FastAPI backend
6. React dashboard later

## Repository Map

- [Master Thesis](docs/00-master-thesis.md)
- [APS Internship Plan](docs/01-aps-internship-plan.md)
- [PV Reliability Research Project](docs/02-pv-reliability-project.md)
- [BESS Analytics Roadmap](docs/03-bess-analytics-roadmap.md)
- [Degradation-Aware EMS Spec](docs/04-degradation-aware-ems-spec.md)
- [Inverter Forensics Roadmap](docs/05-inverter-forensics-roadmap.md)
- [Skill Roadmap](docs/06-skill-roadmap.md)
- [Internship Selection Filter](docs/07-internship-selection-filter.md)
- [90-Day Action Plan](docs/08-90-day-action-plan.md)
- [Project Charter](docs/09-project-charter.md)

## Project Structure

```txt
backend/app/services/
  data_generator.py        Synthetic BESS, PV, load, tariff, and EV session data
  telemetry_validator.py   Data quality and feasibility checks
  battery_health.py        EFC, C-rate, stress, and simple SoH calculations
  degradation_cost.py      Battery lifetime cost and dispatch recommendation
  dispatch_optimizer.py    LP-based dispatch strategy comparison
  report_generator.py      HTML audit report generation

backend/app/main.py         FastAPI application entrypoint

frontend/
  index.html                Lightweight dashboard
  styles.css
  app.js

data/
  sample_bess_telemetry.csv
  sample_site_load.csv
  sample_pv_generation.csv
  sample_tariff.csv
  sample_ev_sessions.csv
  sample_battery_config.csv

tests/
  test_data_foundation.py

reports/
  bess_profitguard_report.html
```

## Quick Start

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Generate sample datasets:

```bash
python3 generate_sample_data.py
```

Validate generated datasets:

```bash
python3 telemetry_validator.py
```

Generate a battery health report:

```bash
python3 battery_health_report.py
```

Generate a degradation cost and dispatch decision report:

```bash
python3 degradation_cost_report.py
```

Compare dispatch strategies:

```bash
python3 dispatch_optimization_report.py
```

Generate the HTML audit report:

```bash
python3 generate_report.py
```

Open the generated file:

```txt
reports/bess_profitguard_report.html
```

Run tests:

```bash
python3 -m pytest -q
```

Run the API server:

```bash
python3 -m uvicorn backend.app.main:app --reload
```

API docs:

```txt
http://127.0.0.1:8000/docs
```

Dashboard:

```txt
http://127.0.0.1:8000/dashboard/
```

## Data Sign Convention

```txt
battery_power_kw > 0  means discharging
battery_power_kw < 0  means charging
battery_power_kw = 0  means idle
```

## Validation Coverage

The current validator checks:

- missing timestamps
- duplicate timestamps
- irregular time intervals
- invalid SoC values
- invalid temperature values
- voltage outliers
- battery power limit violations
- negative load, PV, or tariff values
- EV departure before arrival
- EV energy infeasibility within connection window
- high-temperature exposure warnings
- high-SoC dwell warnings

## Battery Health Metrics

The current Battery Health Engine calculates:

- estimated SoH
- equivalent full cycles
- charge and discharge energy throughput
- net battery energy
- max C-rate
- average active C-rate
- average and max temperature
- high-temperature exposure
- high-SoC dwell
- low-SoC dwell
- active operating hours
- stress score
- low, medium, or high risk level
- human-readable risk reasons

## Degradation Cost Metrics

The current Degradation Cost Engine calculates:

- battery replacement cost
- expected cycle life
- base cost per equivalent full cycle
- stress multiplier
- temperature multiplier
- SoC dwell multiplier
- C-rate multiplier
- SoH multiplier
- estimated degradation cost
- dispatch revenue
- net benefit after degradation cost
- recommendation: dispatch, dispatch with caution, or preserve
- confidence and explanation reasons

## Dispatch Optimization Metrics

The current Dispatch Optimization Engine compares:

- no battery baseline
- energy-cost-only dispatch
- degradation-aware dispatch

The optimizer uses a 24-hour linear program with:

- site load
- PV generation
- import tariff
- export price
- battery charge/discharge power limits
- SoC limits
- reserve SoC
- charge/discharge efficiency
- terminal SoC constraint for fair daily comparison
- degradation cost per discharged kWh

The strategy report includes:

- energy cost
- gross savings
- degradation cost
- net savings
- total charge energy
- total discharge energy
- final SoC
- recommendation
- hourly degradation-aware schedule

## HTML Audit Report

The generated report combines:

- validation status
- battery health metrics
- degradation cost metrics
- no-battery baseline
- energy-cost-only dispatch
- degradation-aware dispatch
- executive recommendation
- risk reasons
- schedule preview

Current sample result:

```txt
No battery cost: ₹19,876.87
Energy-cost-only net savings: ₹2,258.47
Degradation-aware net savings: ₹2,273.73
Recommendation: Use degradation-aware dispatch
```

## API Endpoints

The FastAPI backend exposes:

- `GET /api/status`
- `POST /api/sample-data`
- `POST /api/sessions`
- `POST /api/sessions/{session_id}/upload`
- `GET /api/sessions/{session_id}/files`
- `GET /api/validation`
- `GET /api/battery-health`
- `POST /api/degradation-cost`
- `POST /api/dispatch`
- `POST /api/report`
- `GET /api/report/html`

Example:

```bash
curl http://127.0.0.1:8000/api/status
```

Generate data through the API:

```bash
curl -X POST http://127.0.0.1:8000/api/sample-data \
  -H "Content-Type: application/json" \
  -d '{"output_dir":"data","days":7,"seed":42}'
```

Create an upload session:

```bash
curl -X POST http://127.0.0.1:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"base_dir":"runs"}'
```

Upload a CSV into the session:

```bash
curl -X POST http://127.0.0.1:8000/api/sessions/{session_id}/upload \
  -F "file_type=bess_telemetry" \
  -F "base_dir=runs" \
  -F "file=@data/sample_bess_telemetry.csv"
```

Supported upload `file_type` values:

- `bess_telemetry`
- `site_load`
- `pv_generation`
- `tariff`
- `ev_sessions`
- `battery_config`

After upload, use the returned `data_dir` with the existing validation, health, degradation, dispatch, and report endpoints.

## Security Posture

The MVP includes basic production-safety controls:

- strict Pydantic request schemas with extra fields rejected
- generic validation and server error responses
- server-side exception logging without stack traces in API responses
- explicit CORS origins through `ALLOWED_ORIGINS`
- security headers for API and dashboard responses
- basic in-memory rate limiting for `/api/*`
- upload file size limit through `MAX_UPLOAD_BYTES`
- CSV-only upload checks
- path traversal protection for `data`, `runs`, and `reports`
- FastAPI docs disabled when `APP_ENV=production`

Recommended production environment:

```bash
APP_ENV=production
ALLOWED_ORIGINS=https://your-domain.example
MAX_UPLOAD_BYTES=5242880
RATE_LIMIT_REQUESTS=120
RATE_LIMIT_WINDOW_SECONDS=900
```

The frontend contains no secrets and should be treated as fully public. Business logic and validation remain server-side.

## Dashboard

The dashboard provides:

- API health status
- sample-data generation
- upload session creation
- typed CSV upload controls
- uploaded/missing file status
- data directory and dispatch revenue controls
- validation summary
- battery health KPIs
- degradation cost KPI
- SoC trajectory chart
- battery charge/discharge chart
- grid import chart
- no-battery vs energy-cost-only vs degradation-aware strategy table
- risk reasons
- optimized schedule preview
- link to the HTML audit report

## Company Direction

The long-term company is an energy infrastructure software company, not an energy generation company.

Best one-line thesis:

> We help BESS owners, EV depots, and microgrid operators maximize revenue without destroying battery lifetime or compromising grid reliability.

## Near-Term Focus

The first software wedge is BESS ProfitGuard:

- Battery telemetry validation
- Battery health scoring
- Degradation cost modeling
- Degradation-aware dispatch optimization
- EV depot and commercial microgrid reporting

The immediate next task is to improve the dashboard into a more complete product UI:

- add a persistent report/history view
- keep CLI and API outputs consistent
