from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Optional

from backend.app.services.battery_health import BatteryHealthReport
from backend.app.services.degradation_cost import DegradationCostReport
from backend.app.services.dispatch_optimizer import DispatchComparisonReport, StrategySummary
from backend.app.services.telemetry_validator import ValidationReport


@dataclass(frozen=True)
class ProjectReport:
    title: str
    generated_at: str
    validation_reports: list[ValidationReport]
    health_report: BatteryHealthReport
    degradation_report: DegradationCostReport
    dispatch_report: DispatchComparisonReport
    battery_config: Optional[dict[str, Any]] = None
    sensitivity_analysis: Optional[list[tuple[str, float]]] = None


def _money(value: float, currency: str = "INR") -> str:
    symbol = "₹" if currency == "INR" else f"{currency} "
    return f"{symbol}{value:,.2f}"


def _number(value: float | int | None, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int):
        return f"{value}{suffix}"
    return f"{value:,.2f}{suffix}"


def _status_class(ok: bool) -> str:
    return "ok" if ok else "bad"


def _render_metric_cards(metrics: list[tuple[str, str, str]]) -> str:
    cards = []
    for label, value, note in metrics:
        cards.append(
            "<div class=\"card\">"
            f"<div class=\"label\">{escape(label)}</div>"
            f"<div class=\"value\">{escape(value)}</div>"
            f"<div class=\"note\">{escape(note)}</div>"
            "</div>"
        )
    return "\n".join(cards)


def _render_validation_table(reports: list[ValidationReport]) -> str:
    rows = []
    for report in reports:
        status = "PASS" if report.passed else "FAIL"
        issues = ", ".join(f"{issue.code} ({issue.count})" for issue in report.issues) or "None"
        rows.append(
            "<tr>"
            f"<td>{escape(report.dataset)}</td>"
            f"<td>{report.row_count}</td>"
            f"<td class=\"{_status_class(report.passed)}\">{status}</td>"
            f"<td>{report.error_count}</td>"
            f"<td>{report.warning_count}</td>"
            f"<td>{escape(issues)}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _render_strategy_row(strategy: StrategySummary, currency: str) -> str:
    return (
        "<tr>"
        f"<td>{escape(strategy.strategy)}</td>"
        f"<td>{escape(strategy.status)}</td>"
        f"<td>{escape(_money(strategy.energy_cost, currency))}</td>"
        f"<td>{escape(_money(strategy.gross_savings, currency))}</td>"
        f"<td>{escape(_money(strategy.degradation_cost, currency))}</td>"
        f"<td>{escape(_money(strategy.net_savings, currency))}</td>"
        f"<td>{_number(strategy.total_discharge_energy_kwh, ' kWh')}</td>"
        f"<td>{_number(strategy.final_soc_percent, '%')}</td>"
        "</tr>"
    )


def _render_schedule_rows(schedule: list[dict[str, Any]], limit: int = 12) -> str:
    rows = []
    for item in schedule[:limit]:
        rows.append(
            "<tr>"
            f"<td>{escape(str(item['timestamp']))}</td>"
            f"<td>{_number(float(item['charge_kw']), ' kW')}</td>"
            f"<td>{_number(float(item['discharge_kw']), ' kW')}</td>"
            f"<td>{_number(float(item['soc_percent']), '%')}</td>"
            f"<td>{_number(float(item['grid_import_kw']), ' kW')}</td>"
            f"<td>{_number(float(item['energy_price_per_kwh']), '/kWh')}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _config_value(config: Optional[dict[str, Any]], key: str, fallback: Any = None) -> Any:
    if not config:
        return fallback
    return config.get(key, fallback)


def render_html_report(report: ProjectReport) -> str:
    currency = report.degradation_report.currency
    validation_passed = all(item.passed for item in report.validation_reports)
    health = report.health_report
    degradation = report.degradation_report
    dispatch = report.dispatch_report

    headline_metrics = [
        ("Validation", "PASS" if validation_passed else "FAIL", "Data quality gate"),
        ("Battery Risk", health.risk_level.upper(), f"Stress score {health.stress_score:.2f}/100"),
        ("SoH", _number(health.estimated_soh_percent, "%"), "Simple health estimate"),
        ("Degradation Cost", _money(degradation.estimated_degradation_cost, currency), "Telemetry-based lifetime cost"),
        ("Best Net Savings", _money(dispatch.degradation_aware.net_savings, currency), "24-hour degradation-aware dispatch"),
        ("Recommendation", dispatch.degradation_aware.strategy, "Selected schedule basis"),
    ]

    risk_reasons = "".join(f"<li>{escape(reason)}</li>" for reason in health.risk_reasons + degradation.reasons)
    if not risk_reasons:
        risk_reasons = "<li>No material battery risk reasons detected in this sample.</li>"

    battery_config = report.battery_config or {}
    assumptions = [
        ("Battery chemistry", _config_value(battery_config, "chemistry", "n/a")),
        ("Nameplate capacity", _number(_config_value(battery_config, "battery_capacity_kwh"), " kWh")),
        ("Usable capacity", _number(_config_value(battery_config, "usable_capacity_kwh"), " kWh")),
        ("Reserve SoC", _number(_config_value(battery_config, "reserve_soc_percent"), "%")),
        ("Allowed SoC window", f"{_number(_config_value(battery_config, 'min_soc_percent'), '%')} to {_number(_config_value(battery_config, 'max_soc_percent'), '%')}"),
        ("Max charge power", _number(_config_value(battery_config, "max_charge_power_kw"), " kW")),
        ("Max discharge power", _number(_config_value(battery_config, "max_discharge_power_kw"), " kW")),
        ("Replacement cost", _money(float(_config_value(battery_config, "replacement_cost", degradation.replacement_cost)), currency)),
        ("Expected cycle life", _number(_config_value(battery_config, "expected_cycle_life", degradation.expected_cycle_life), " cycles")),
        ("Forecast horizon", "24-hour dispatch optimization"),
    ]
    assumption_rows = "\n".join(
        f"<tr><th>{escape(label)}</th><td>{escape(str(value))}</td></tr>" for label, value in assumptions
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escape(report.title)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; color: #17202a; margin: 32px; line-height: 1.45; }}
    h1, h2 {{ margin-bottom: 8px; }}
    .subtitle {{ color: #5d6d7e; margin-top: 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin: 18px 0 28px; }}
    .card {{ border: 1px solid #d6dbdf; border-radius: 8px; padding: 14px; background: #fbfcfc; }}
    .label {{ color: #5d6d7e; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    .value {{ font-size: 22px; font-weight: 700; margin: 6px 0; }}
    .note {{ color: #5d6d7e; font-size: 13px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 26px; font-size: 14px; }}
    th, td {{ border: 1px solid #d6dbdf; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f5; }}
    .ok {{ color: #117a65; font-weight: 700; }}
    .bad {{ color: #b03a2e; font-weight: 700; }}
    .callout {{ border-left: 4px solid #1f618d; background: #f4f8fb; padding: 12px 14px; margin: 16px 0 26px; }}
    .small {{ color: #5d6d7e; font-size: 12px; }}
  </style>
</head>
<body>
  <h1>{escape(report.title)}</h1>
  <p class="subtitle">Generated at {escape(report.generated_at)}. Battery-aware EMS audit for BESS and EV charging site operation.</p>

  <div class="grid">
    {_render_metric_cards(headline_metrics)}
  </div>

  <h2>Executive Recommendation</h2>
  <div class="callout">
    <strong>Recommended Strategy: {escape(dispatch.degradation_aware.strategy)}</strong>
    <p><strong>Why:</strong></p>
    <ul>
      <li>Net savings are higher than energy-cost-only dispatch.</li>
      <li>Battery stress is reduced.</li>
      <li>Reserve SoC is maintained.</li>
      <li>Degradation cost is explicitly accounted for.</li>
    </ul>
    <p><strong>Action:</strong></p>
    <p>Discharge only during the highest-value hours. Avoid low-value cycling.</p>
  </div>

  <h2>Data Validation</h2>
  <table>
    <thead><tr><th>Dataset</th><th>Rows</th><th>Status</th><th>Errors</th><th>Warnings</th><th>Issues</th></tr></thead>
    <tbody>{_render_validation_table(report.validation_reports)}</tbody>
  </table>

  <h2>Battery Health</h2>
  <table>
    <tbody>
      <tr><th>Estimated SoH</th><td>{_number(health.estimated_soh_percent, "%")}</td></tr>
      <tr><th>Equivalent Full Cycles</th><td>{_number(health.equivalent_full_cycles)}</td></tr>
      <tr><th>Discharge Energy</th><td>{_number(health.total_discharge_energy_kwh, " kWh")}</td></tr>
      <tr><th>Max C-rate</th><td>{_number(health.max_c_rate, "C")}</td></tr>
      <tr><th>High Temperature Exposure</th><td>{_number(health.high_temperature_hours, " h")}</td></tr>
      <tr><th>High SoC Dwell</th><td>{_number(health.high_soc_dwell_hours, " h")}</td></tr>
      <tr><th>Low SoC Dwell</th><td>{_number(health.low_soc_dwell_hours, " h")}</td></tr>
      <tr><th>Risk Level</th><td>{escape(health.risk_level)}</td></tr>
    </tbody>
  </table>

  <h2>Degradation Cost</h2>
  <table>
    <tbody>
      <tr><th>Replacement Cost</th><td>{_money(degradation.replacement_cost, currency)}</td></tr>
      <tr><th>Expected Cycle Life</th><td>{_number(degradation.expected_cycle_life, " cycles")}</td></tr>
      <tr><th>Base Cycle Cost</th><td>{_money(degradation.base_cycle_cost, currency)}</td></tr>
      <tr><th>Stress Multiplier</th><td>{_number(degradation.stress_multiplier)}</td></tr>
      <tr><th>Estimated Degradation Cost</th><td>{_money(degradation.estimated_degradation_cost, currency)}</td></tr>
      <tr><th>Dispatch Revenue Assumption</th><td>{_money(degradation.dispatch_revenue, currency)}</td></tr>
      <tr><th>Net Benefit</th><td>{_money(degradation.net_benefit, currency)}</td></tr>
      <tr><th>Standalone Recommendation</th><td>{escape(degradation.recommendation)}</td></tr>
    </tbody>
  </table>

  <h2>Dispatch Strategy Comparison</h2>
  <table>
    <thead>
      <tr><th>Strategy</th><th>Status</th><th>Energy Cost</th><th>Gross Savings</th><th>Degradation Cost</th><th>Net Savings</th><th>Discharge Energy</th><th>Final SoC</th></tr>
    </thead>
    <tbody>
      {_render_strategy_row(dispatch.baseline, currency)}
      {_render_strategy_row(dispatch.energy_cost_only, currency)}
      {_render_strategy_row(dispatch.degradation_aware, currency)}
    </tbody>
  </table>

  <h2>Risk Reasons</h2>
  <ul>{risk_reasons}</ul>

  <h2>Assumptions and Limitations</h2>
  <table>
    <tbody>{assumption_rows}</tbody>
  </table>

  <h2>Sensitivity Analysis</h2>
  <table>
    <thead><tr><th>Scenario</th><th>Net Savings</th></tr></thead>
    <tbody>
      {"".join(f"<tr><td>{escape(label)}</td><td>{escape(_money(val, currency))}</td></tr>" for label, val in (report.sensitivity_analysis or []))}
    </tbody>
  </table>
  <div class="callout">
    <strong>Decision-support model, not OEM certification.</strong>
    <p>This report estimates operational and financial tradeoffs from the supplied telemetry, tariff, load, PV, and battery configuration. It is not a manufacturer-certified degradation prediction, warranty opinion, or live control command.</p>
    <p>Production deployment should validate forecasts, BMS measurements, site interconnection limits, OEM warranty constraints, and safety controls before any automated dispatch action.</p>
  </div>

  <h2>Schedule Preview</h2>
  <table>
    <thead><tr><th>Timestamp</th><th>Charge</th><th>Discharge</th><th>SoC</th><th>Grid Import</th><th>Energy Price</th></tr></thead>
    <tbody>{_render_schedule_rows(dispatch.schedule)}</tbody>
  </table>
  <p class="small">Schedule preview is limited to the first 12 rows. Full schedule is available in the dispatch report object.</p>
</body>
</html>
"""
    return html


def write_html_report(report: ProjectReport, output_path: Path | str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html_report(report), encoding="utf-8")
    return path


def build_project_report(
    validation_reports: list[ValidationReport],
    health_report: BatteryHealthReport,
    degradation_report: DegradationCostReport,
    dispatch_report: DispatchComparisonReport,
    battery_config: Optional[dict[str, Any]] = None,
    sensitivity_analysis: Optional[list[tuple[str, float]]] = None,
    title: str = "BESS ProfitGuard Dispatch Audit",
) -> ProjectReport:
    return ProjectReport(
        title=title,
        generated_at=datetime.now().replace(microsecond=0).isoformat(),
        validation_reports=validation_reports,
        health_report=health_report,
        degradation_report=degradation_report,
        dispatch_report=dispatch_report,
        battery_config=battery_config,
        sensitivity_analysis=sensitivity_analysis,
    )
