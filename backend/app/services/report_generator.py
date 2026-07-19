# BESS ProfitGuard: report_generator.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Optional

from backend.app.services.battery_health import BatteryHealthReport
from backend.app.services.degradation_cost import DegradationCostReport
from backend.app.services.dispatch_optimizer import DispatchComparisonReport, StrategySummary
from backend.app.services.demand_charge import compare_demand_charge
from backend.app.services.operating_modes import get_operating_mode
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


def _percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f}%"


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
        f"<td>{escape(_money(strategy.demand_charge_cost, currency))}</td>"
        f"<td>{escape(_money(strategy.gross_savings, currency))}</td>"
        f"<td>{escape(_money(strategy.degradation_cost, currency))}</td>"
        f"<td>{escape(_money(strategy.net_savings, currency))}</td>"
        f"<td>{_percent(strategy.ev_readiness_percent)}</td>"
        f"<td>{_number(strategy.peak_grid_import_kw, ' kW')}</td>"
        f"<td>{_number(strategy.total_discharge_energy_kwh, ' kWh')}</td>"
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


def _data_quality_score(validation_reports: list[ValidationReport]) -> float:
    total_rows = sum(report.row_count for report in validation_reports) or 1
    error_penalty = sum(report.error_count * 20 for report in validation_reports)
    warning_penalty = sum(report.warning_count * 4 for report in validation_reports)
    issue_density_penalty = sum(len(report.issues) for report in validation_reports) / total_rows * 100
    return round(max(0.0, min(100.0, 100.0 - error_penalty - warning_penalty - issue_density_penalty)), 1)


def _confidence_score(validation_score: float, health: BatteryHealthReport, dispatch: DispatchComparisonReport) -> tuple[float, str]:
    score = validation_score
    if health.risk_level == "medium":
        score -= 8
    elif health.risk_level == "high":
        score -= 18
    if dispatch.degradation_aware.status != "optimal":
        score -= 35
    if dispatch.degradation_aware.net_savings < 0:
        score -= 12
    bounded = round(max(0.0, min(100.0, score)), 1)
    if bounded >= 85:
        label = "High"
    elif bounded >= 70:
        label = "Medium"
    else:
        label = "Low"
    return bounded, label


def _operating_policy(dispatch: DispatchComparisonReport) -> list[str]:
    policy = [
        "Use degradation-aware dispatch as the default operating policy for this horizon.",
        "Preserve reserve SoC before low-value cycling or uncertain EV demand periods.",
        "Discharge during the highest-value tariff and peak-shaving windows.",
    ]
    if dispatch.degradation_aware.total_discharge_energy_kwh < dispatch.energy_cost_only.total_discharge_energy_kwh:
        policy.append("Limit extra discharge because energy-cost-only dispatch uses more battery lifetime for lower net value.")
    if dispatch.degradation_aware.peak_grid_import_kw < dispatch.baseline.peak_grid_import_kw:
        policy.append("Use the BESS to cap site peak import where demand charges are active.")
    return policy


def render_html_report(report: ProjectReport) -> str:
    currency = report.degradation_report.currency
    validation_passed = all(item.passed for item in report.validation_reports)
    health = report.health_report
    degradation = report.degradation_report
    dispatch = report.dispatch_report
    mode_config = get_operating_mode(dispatch.operating_mode)
    demand_rate = (
        dispatch.baseline.demand_charge_cost / dispatch.baseline.peak_grid_import_kw
        if dispatch.baseline.peak_grid_import_kw
        else 0.0
    )
    demand_metrics = compare_demand_charge(
        dispatch.baseline.peak_grid_import_kw,
        dispatch.degradation_aware.peak_grid_import_kw,
        demand_rate,
    )
    data_quality_score = _data_quality_score(report.validation_reports)
    confidence_score, confidence_label = _confidence_score(data_quality_score, health, dispatch)
    daily_net_savings = dispatch.degradation_aware.net_savings
    monthly_net_savings = daily_net_savings * 30
    annual_net_savings = daily_net_savings * 365
    cost_only_extra_degradation = dispatch.energy_cost_only.degradation_cost - dispatch.degradation_aware.degradation_cost
    peak_reduction_kw = max(0.0, dispatch.baseline.peak_grid_import_kw - dispatch.degradation_aware.peak_grid_import_kw)
    demand_charge_savings = max(0.0, dispatch.baseline.demand_charge_cost - dispatch.degradation_aware.demand_charge_cost)

    headline_metrics = [
        ("Data Quality", _percent(data_quality_score), "Validation confidence"),
        ("Battery Risk", health.risk_level.upper(), f"Stress score {health.stress_score:.2f}/100"),
        ("SoH", _number(health.estimated_soh_percent, "%"), "Simple health estimate"),
        ("Monthly Net Savings", _money(monthly_net_savings, currency), "30-day projection"),
        ("Peak Reduction", _number(peak_reduction_kw, " kW"), "Demand-charge exposure"),
        ("EV Readiness", _percent(dispatch.degradation_aware.ev_readiness_percent), "Departure reliability"),
        ("Confidence", f"{confidence_label} ({_percent(confidence_score)})", "Audit confidence"),
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
        ("Operating mode", mode_config.label),
    ]
    assumption_rows = "\n".join(
        f"<tr><th>{escape(label)}</th><td>{escape(str(value))}</td></tr>" for label, value in assumptions
    )
    operating_policy = "".join(f"<li>{escape(item)}</li>" for item in _operating_policy(dispatch))
    stress_events = [
        ("High temperature exposure", _number(health.high_temperature_hours, " h"), "Thermal stress can accelerate battery aging."),
        ("High SoC dwell", _number(health.high_soc_dwell_hours, " h"), "Long high-SoC dwell can increase calendar aging."),
        ("Low SoC dwell", _number(health.low_soc_dwell_hours, " h"), "Low reserve periods reduce operating flexibility."),
        ("Max C-rate", _number(health.max_c_rate, "C"), "High C-rate operation increases cycling stress."),
    ]
    stress_rows = "\n".join(
        f"<tr><td>{escape(label)}</td><td>{escape(value)}</td><td>{escape(note)}</td></tr>"
        for label, value, note in stress_events
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

  <h2>Executive Summary</h2>
  <div class="callout">
    <strong>Recommended Strategy: {escape(dispatch.degradation_aware.strategy)}</strong>
    <p>{escape(dispatch.recommendation)}</p>
    <p><strong>Operating mode:</strong> {escape(mode_config.label)}. {escape(mode_config.description)}</p>
    <p><strong>Estimated 24-hour net savings:</strong> {_money(daily_net_savings, currency)}. <strong>Projected monthly net savings:</strong> {_money(monthly_net_savings, currency)}.</p>
    <p><strong>Peak demand reduced from</strong> {_number(dispatch.baseline.peak_grid_import_kw, " kW")} <strong>to</strong> {_number(dispatch.degradation_aware.peak_grid_import_kw, " kW")}. <strong>Modeled demand-charge savings:</strong> {_money(demand_charge_savings, currency)}.</p>
    <p><strong>EV readiness:</strong> {_percent(dispatch.degradation_aware.ev_readiness_percent)} overall and {_percent(dispatch.degradation_aware.priority_ev_readiness_percent)} for priority EVs.</p>
  </div>

  <h2>Recommended Operating Policy</h2>
  <div class="callout">
    <ul>
      {operating_policy}
    </ul>
  </div>

  <h2>Site Assumptions</h2>
  <table>
    <tbody>{assumption_rows}</tbody>
  </table>

  <h2>Data Quality Score</h2>
  <div class="callout">
    <strong>{_percent(data_quality_score)} data quality score</strong>
    <p>Validation status: {"PASS" if validation_passed else "FAIL"}. Confidence is {escape(confidence_label.lower())} because model confidence combines data quality, battery stress, and optimizer status.</p>
  </div>
  <table>
    <thead><tr><th>Dataset</th><th>Rows</th><th>Status</th><th>Errors</th><th>Warnings</th><th>Issues</th></tr></thead>
    <tbody>{_render_validation_table(report.validation_reports)}</tbody>
  </table>

  <h2>Battery Health Summary</h2>
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

  <h2>Revenue vs Degradation Cost</h2>
  <table>
    <tbody>
      <tr><th>Replacement Cost</th><td>{_money(degradation.replacement_cost, currency)}</td></tr>
      <tr><th>Expected Cycle Life</th><td>{_number(degradation.expected_cycle_life, " cycles")}</td></tr>
      <tr><th>Base Cycle Cost</th><td>{_money(degradation.base_cycle_cost, currency)}</td></tr>
      <tr><th>Stress Multiplier</th><td>{_number(degradation.stress_multiplier)}</td></tr>
      <tr><th>Estimated Degradation Cost</th><td>{_money(degradation.estimated_degradation_cost, currency)}</td></tr>
      <tr><th>Dispatch Revenue Assumption</th><td>{_money(degradation.dispatch_revenue, currency)}</td></tr>
      <tr><th>Net Benefit</th><td>{_money(degradation.net_benefit, currency)}</td></tr>
      <tr><th>Cost-Only Extra Degradation</th><td>{_money(cost_only_extra_degradation, currency)}</td></tr>
      <tr><th>Standalone Recommendation</th><td>{escape(degradation.recommendation)}</td></tr>
    </tbody>
  </table>

  <h2>Dispatch Strategy Comparison</h2>
  <table>
    <thead>
      <tr><th>Strategy</th><th>Status</th><th>Energy Cost</th><th>Demand Charge</th><th>Gross Savings</th><th>Degradation Cost</th><th>Net Savings</th><th>EV Readiness</th><th>Peak Demand</th><th>Discharge Energy</th></tr>
    </thead>
    <tbody>
      {_render_strategy_row(dispatch.baseline, currency)}
      {_render_strategy_row(dispatch.energy_cost_only, currency)}
      {_render_strategy_row(dispatch.degradation_aware, currency)}
    </tbody>
  </table>

  <h2>Monthly Net Savings</h2>
  <table>
    <tbody>
      <tr><th>Daily Net Savings</th><td>{_money(daily_net_savings, currency)}</td></tr>
      <tr><th>Projected Monthly Net Savings</th><td>{_money(monthly_net_savings, currency)}</td></tr>
      <tr><th>Projected Annual Net Savings</th><td>{_money(annual_net_savings, currency)}</td></tr>
      <tr><th>Demand Charge Savings</th><td>{_money(demand_charge_savings, currency)}</td></tr>
      <tr><th>Monthly Peak-Shaving Savings</th><td>{_money(demand_metrics.monthly_peak_shaving_savings, currency)}</td></tr>
      <tr><th>Peak Demand Reduction</th><td>{_number(peak_reduction_kw, " kW")}</td></tr>
      <tr><th>Unmet EV Energy</th><td>{_number(dispatch.degradation_aware.unmet_ev_energy_kwh, " kWh")}</td></tr>
    </tbody>
  </table>

  <h2>Battery Stress Events</h2>
  <table>
    <thead><tr><th>Event</th><th>Measured Value</th><th>Meaning</th></tr></thead>
    <tbody>{stress_rows}</tbody>
  </table>
  <ul>{risk_reasons}</ul>

  <h2>Assumptions and Limitations</h2>
  <div class="callout">
    <strong>Decision-support model, not OEM certification.</strong>
    <p>This report estimates operational and financial tradeoffs from the supplied telemetry, tariff, load, PV, and battery configuration. It is not a manufacturer-certified degradation prediction, warranty opinion, or live control command.</p>
    <p>Production deployment should validate forecasts, BMS measurements, site interconnection limits, OEM warranty constraints, and safety controls before any automated dispatch action.</p>
  </div>

  <h2>Sensitivity Analysis</h2>
  <table>
    <thead><tr><th>Scenario</th><th>Net Savings</th></tr></thead>
    <tbody>
      {"".join(f"<tr><td>{escape(label)}</td><td>{escape(_money(val, currency))}</td></tr>" for label, val in (report.sensitivity_analysis or []))}
    </tbody>
  </table>

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
