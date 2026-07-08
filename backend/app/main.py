from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.app.services.battery_health import calculate_battery_health
from backend.app.services.data_generator import SampleDataConfig, generate_sample_data
from backend.app.services.degradation_cost import calculate_degradation_cost
from backend.app.services.dispatch_optimizer import compare_dispatch_strategies
from backend.app.services.report_generator import build_project_report, render_html_report, write_html_report
from backend.app.services.telemetry_validator import load_battery_config, validate_generated_dataset


class GenerateSampleDataRequest(BaseModel):
    output_dir: str = "data"
    days: int = Field(default=7, ge=1, le=30)
    seed: int = 42


class DegradationRequest(BaseModel):
    data_dir: str = "data"
    dispatch_revenue: float = 7500.0


class DispatchRequest(BaseModel):
    data_dir: str = "data"
    dispatch_revenue: float = 7500.0


class ReportRequest(BaseModel):
    data_dir: str = "data"
    output_path: str = "reports/bess_profitguard_report.html"
    dispatch_revenue: float = 7500.0


class CreateSessionRequest(BaseModel):
    base_dir: str = "runs"


EXPECTED_UPLOAD_FILES = {
    "bess_telemetry": "sample_bess_telemetry.csv",
    "site_load": "sample_site_load.csv",
    "pv_generation": "sample_pv_generation.csv",
    "tariff": "sample_tariff.csv",
    "ev_sessions": "sample_ev_sessions.csv",
    "battery_config": "sample_battery_config.csv",
}


app = FastAPI(
    title="BESS ProfitGuard API",
    version="0.1.0",
    description="Battery-aware EMS API for BESS health, degradation cost, and dispatch optimization.",
)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/dashboard", StaticFiles(directory=FRONTEND_DIR, html=True), name="dashboard")


def _session_path(session_id: str, base_dir: str = "runs") -> Path:
    if not session_id or any(char in session_id for char in ("/", "\\", "..")):
        raise HTTPException(status_code=400, detail="Invalid session_id.")
    return Path(base_dir) / session_id


def _data_path(data_dir: str) -> Path:
    return Path(data_dir)


def _load_inputs(data_dir: str) -> dict[str, Any]:
    data_path = _data_path(data_dir)
    battery_config = load_battery_config(data_path / "sample_battery_config.csv")
    return {
        "battery_config": battery_config,
        "telemetry": pd.read_csv(data_path / "sample_bess_telemetry.csv"),
        "site_load": pd.read_csv(data_path / "sample_site_load.csv"),
        "pv_generation": pd.read_csv(data_path / "sample_pv_generation.csv"),
        "tariff": pd.read_csv(data_path / "sample_tariff.csv"),
    }


def _build_pipeline(data_dir: str, dispatch_revenue: float) -> dict[str, Any]:
    inputs = _load_inputs(data_dir)
    validation = validate_generated_dataset(data_dir)
    health = calculate_battery_health(inputs["telemetry"], inputs["battery_config"])
    degradation = calculate_degradation_cost(health, dict(inputs["battery_config"]), dispatch_revenue=dispatch_revenue)
    dispatch = compare_dispatch_strategies(
        site_load=inputs["site_load"],
        pv_generation=inputs["pv_generation"],
        tariff=inputs["tariff"],
        battery_config=inputs["battery_config"],
        degradation_stress_multiplier=degradation.stress_multiplier,
    )
    return {
        "validation": validation,
        "health": health,
        "degradation": degradation,
        "dispatch": dispatch,
    }


@app.get("/api/status")
def status() -> dict[str, str]:
    return {"status": "ok", "service": "BESS ProfitGuard API"}


@app.post("/api/sample-data")
def generate_sample_data_endpoint(request: GenerateSampleDataRequest) -> dict[str, Any]:
    config = SampleDataConfig(days=request.days, seed=request.seed)
    written = generate_sample_data(request.output_dir, config)
    return {"output_dir": request.output_dir, "files": {name: str(path) for name, path in written.items()}}


@app.post("/api/sessions")
def create_session(request: Optional[CreateSessionRequest] = None) -> dict[str, str]:
    request = request or CreateSessionRequest()
    session_id = uuid4().hex
    path = _session_path(session_id, request.base_dir)
    path.mkdir(parents=True, exist_ok=False)
    return {"session_id": session_id, "data_dir": str(path)}


@app.post("/api/sessions/{session_id}/upload")
async def upload_session_file(
    session_id: str,
    file_type: str = Form(...),
    file: UploadFile = File(...),
    base_dir: str = Form("runs"),
) -> dict[str, str]:
    if file_type not in EXPECTED_UPLOAD_FILES:
        allowed = ", ".join(sorted(EXPECTED_UPLOAD_FILES))
        raise HTTPException(status_code=400, detail=f"Unsupported file_type. Allowed: {allowed}")
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV uploads are supported.")

    session_dir = _session_path(session_id, base_dir)
    session_dir.mkdir(parents=True, exist_ok=True)
    destination = session_dir / EXPECTED_UPLOAD_FILES[file_type]
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    destination.write_bytes(contents)
    return {"session_id": session_id, "file_type": file_type, "path": str(destination)}


@app.get("/api/sessions/{session_id}/files")
def list_session_files(session_id: str, base_dir: str = "runs") -> dict[str, Any]:
    session_dir = _session_path(session_id, base_dir)
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Session not found.")
    files = {
        file_type: str(session_dir / filename)
        for file_type, filename in EXPECTED_UPLOAD_FILES.items()
        if (session_dir / filename).exists()
    }
    missing = sorted(file_type for file_type, filename in EXPECTED_UPLOAD_FILES.items() if not (session_dir / filename).exists())
    return {"session_id": session_id, "data_dir": str(session_dir), "files": files, "missing": missing}


@app.get("/api/validation")
def validation_report(data_dir: str = "data") -> dict[str, Any]:
    reports = validate_generated_dataset(data_dir)
    return {"reports": [report.to_dict() for report in reports]}


@app.get("/api/battery-health")
def battery_health_report(data_dir: str = "data") -> dict[str, Any]:
    inputs = _load_inputs(data_dir)
    return calculate_battery_health(inputs["telemetry"], inputs["battery_config"]).to_dict()


@app.post("/api/degradation-cost")
def degradation_cost_report(request: DegradationRequest) -> dict[str, Any]:
    pipeline = _build_pipeline(request.data_dir, request.dispatch_revenue)
    return pipeline["degradation"].to_dict()


@app.post("/api/dispatch")
def dispatch_report(request: DispatchRequest) -> dict[str, Any]:
    pipeline = _build_pipeline(request.data_dir, request.dispatch_revenue)
    return pipeline["dispatch"].to_dict()


@app.post("/api/report")
def report_json(request: ReportRequest) -> dict[str, Any]:
    pipeline = _build_pipeline(request.data_dir, request.dispatch_revenue)
    project_report = build_project_report(
        pipeline["validation"],
        pipeline["health"],
        pipeline["degradation"],
        pipeline["dispatch"],
    )
    written = write_html_report(project_report, request.output_path)
    return {
        "output_path": str(written),
        "validation_passed": all(report.passed for report in pipeline["validation"]),
        "dispatch_recommendation": pipeline["dispatch"].recommendation,
        "degradation_aware_net_savings": pipeline["dispatch"].degradation_aware.net_savings,
    }


@app.get("/api/report/html", response_class=HTMLResponse)
def report_html(data_dir: str = "data", dispatch_revenue: float = 7500.0) -> str:
    pipeline = _build_pipeline(data_dir, dispatch_revenue)
    project_report = build_project_report(
        pipeline["validation"],
        pipeline["health"],
        pipeline["degradation"],
        pipeline["dispatch"],
    )
    return render_html_report(project_report)
