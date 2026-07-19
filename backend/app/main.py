# BESS ProfitGuard: main.py

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Literal, Optional
from uuid import uuid4

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from backend.app.services.battery_health import calculate_battery_health
from backend.app.services.data_generator import SampleDataConfig, generate_sample_data
from backend.app.services.degradation_cost import calculate_degradation_cost
from backend.app.services.dispatch_optimizer import compare_dispatch_strategies
from backend.app.services.report_generator import build_project_report, render_html_report, write_html_report
from backend.app.services.telemetry_validator import load_battery_config, validate_generated_dataset


logger = logging.getLogger("bess_profitguard")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV = os.getenv("APP_ENV", "development").lower()
IS_PRODUCTION = ENV == "production"
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "120"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "900"))
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",")
    if origin.strip()
]
RATE_LIMIT_BUCKETS: dict[str, list[float]] = {}


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenerateSampleDataRequest(StrictBaseModel):
    output_dir: str = "data"
    days: int = Field(default=7, ge=1, le=30)
    seed: int = 42


class DegradationRequest(StrictBaseModel):
    data_dir: str = "data"
    dispatch_revenue: float = 7500.0


OperatingModeName = Literal["profit_mode", "battery_protection_mode", "ev_readiness_mode"]


class DispatchRequest(StrictBaseModel):
    data_dir: str = "data"
    dispatch_revenue: float = 7500.0
    operating_mode: OperatingModeName = "profit_mode"


class ReportRequest(StrictBaseModel):
    data_dir: str = "data"
    output_path: str = "reports/bess_profitguard_report.html"
    dispatch_revenue: float = 7500.0
    operating_mode: OperatingModeName = "profit_mode"


class CreateSessionRequest(StrictBaseModel):
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
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

FRONTEND_DIR = PROJECT_ROOT / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/dashboard", StaticFiles(directory=FRONTEND_DIR, html=True), name="dashboard")


@app.middleware("http")
async def security_headers_and_rate_limit(request: Request, call_next: Any) -> Any:
    if request.url.path.startswith("/api/"):
        client_host = request.client.host if request.client else "unknown"
        now = time.monotonic()
        bucket = [stamp for stamp in RATE_LIMIT_BUCKETS.get(client_host, []) if now - stamp < RATE_LIMIT_WINDOW_SECONDS]
        if len(bucket) >= RATE_LIMIT_REQUESTS:
            return JSONResponse(status_code=429, content={"error": "Too many requests"})
        bucket.append(now)
        RATE_LIMIT_BUCKETS[client_host] = bucket

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("Validation error on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=422, content={"error": "Invalid request"})


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"error": "Something went wrong"})


def _safe_relative_path(value: str, default: str, allowed_roots: tuple[str, ...]) -> Path:
    candidate = Path(value or default)
    if candidate.is_absolute() or any(part in {"..", ""} for part in candidate.parts):
        raise HTTPException(status_code=400, detail="Invalid path.")
    if candidate.parts and candidate.parts[0] not in allowed_roots:
        allowed = ", ".join(allowed_roots)
        raise HTTPException(status_code=400, detail=f"Path must be under one of: {allowed}")
    resolved = (PROJECT_ROOT / candidate).resolve()
    if not str(resolved).startswith(str(PROJECT_ROOT.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path.")
    return resolved


def _session_path(session_id: str, base_dir: str = "runs") -> Path:
    if not session_id or any(char in session_id for char in ("/", "\\", "..")):
        raise HTTPException(status_code=400, detail="Invalid session_id.")
    return _safe_relative_path(base_dir, "runs", ("runs",)) / session_id


def _session_relative_path(session_id: str, base_dir: str = "runs") -> str:
    if not session_id or any(char in session_id for char in ("/", "\\", "..")):
        raise HTTPException(status_code=400, detail="Invalid session_id.")
    candidate = Path(base_dir or "runs") / session_id
    if candidate.is_absolute() or any(part in {"..", ""} for part in candidate.parts):
        raise HTTPException(status_code=400, detail="Invalid path.")
    return str(candidate)


def _data_path(data_dir: str) -> Path:
    return _safe_relative_path(data_dir, "data", ("data", "runs"))


def _report_path(output_path: str) -> Path:
    return _safe_relative_path(output_path, "reports/bess_profitguard_report.html", ("reports", "runs"))


def _load_inputs(data_dir: str) -> dict[str, Any]:
    data_path = _data_path(data_dir)
    battery_config = load_battery_config(data_path / "sample_battery_config.csv")
    return {
        "battery_config": battery_config,
        "telemetry": pd.read_csv(data_path / "sample_bess_telemetry.csv"),
        "site_load": pd.read_csv(data_path / "sample_site_load.csv"),
        "pv_generation": pd.read_csv(data_path / "sample_pv_generation.csv"),
        "tariff": pd.read_csv(data_path / "sample_tariff.csv"),
        "ev_sessions": pd.read_csv(data_path / "sample_ev_sessions.csv"),
    }


def _build_pipeline(data_dir: str, dispatch_revenue: float, operating_mode: str = "profit_mode") -> dict[str, Any]:
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
        ev_sessions=inputs["ev_sessions"],
        operating_mode=operating_mode,
    )
    dispatch_high = compare_dispatch_strategies(
        site_load=inputs["site_load"],
        pv_generation=inputs["pv_generation"],
        tariff=inputs["tariff"],
        battery_config=inputs["battery_config"],
        degradation_stress_multiplier=degradation.stress_multiplier * 1.5,
        ev_sessions=inputs["ev_sessions"],
        operating_mode=operating_mode,
    )
    dispatch_low = compare_dispatch_strategies(
        site_load=inputs["site_load"],
        pv_generation=inputs["pv_generation"],
        tariff=inputs["tariff"],
        battery_config=inputs["battery_config"],
        degradation_stress_multiplier=degradation.stress_multiplier * 0.5,
        ev_sessions=inputs["ev_sessions"],
        operating_mode=operating_mode,
    )
    sensitivity_analysis = [
        ("Base case", dispatch.degradation_aware.net_savings),
        ("High degradation cost (+50%)", dispatch_high.degradation_aware.net_savings),
        ("Low degradation cost (-50%)", dispatch_low.degradation_aware.net_savings),
    ]

    return {
        "battery_config": inputs["battery_config"],
        "validation": validation,
        "health": health,
        "degradation": degradation,
        "dispatch": dispatch,
        "sensitivity": sensitivity_analysis,
    }


@app.get("/api/status")
def status() -> dict[str, str]:
    return {"status": "ok", "service": "BESS ProfitGuard API"}


@app.post("/api/sample-data")
def generate_sample_data_endpoint(request: GenerateSampleDataRequest) -> dict[str, Any]:
    config = SampleDataConfig(days=request.days, seed=request.seed)
    output_dir = _safe_relative_path(request.output_dir, "data", ("data", "runs"))
    written = generate_sample_data(output_dir, config)
    return {"output_dir": str(output_dir), "files": {name: str(path) for name, path in written.items()}}


@app.post("/api/sessions")
def create_session(request: Optional[CreateSessionRequest] = None) -> dict[str, str]:
    request = request or CreateSessionRequest()
    session_id = uuid4().hex
    path = _session_path(session_id, request.base_dir)
    path.mkdir(parents=True, exist_ok=False)
    return {"session_id": session_id, "data_dir": _session_relative_path(session_id, request.base_dir)}


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
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file is too large.")
    if b"\x00" in contents[:1024]:
        raise HTTPException(status_code=400, detail="Uploaded file must be text CSV.")
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
    return {"session_id": session_id, "data_dir": _session_relative_path(session_id, base_dir), "files": files, "missing": missing}


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
    pipeline = _build_pipeline(request.data_dir, request.dispatch_revenue, request.operating_mode)
    return pipeline["dispatch"].to_dict()


@app.post("/api/report")
def report_json(request: ReportRequest) -> dict[str, Any]:
    pipeline = _build_pipeline(request.data_dir, request.dispatch_revenue, request.operating_mode)
    project_report = build_project_report(
        pipeline["validation"],
        pipeline["health"],
        pipeline["degradation"],
        pipeline["dispatch"],
        battery_config=dict(pipeline["battery_config"]),
        sensitivity_analysis=pipeline["sensitivity"],
    )
    written = write_html_report(project_report, _report_path(request.output_path))
    return {
        "output_path": str(written),
        "validation_passed": all(report.passed for report in pipeline["validation"]),
        "dispatch_recommendation": pipeline["dispatch"].recommendation,
        "degradation_aware_net_savings": pipeline["dispatch"].degradation_aware.net_savings,
    }


@app.get("/api/report/html", response_class=HTMLResponse)
def report_html(data_dir: str = "data", dispatch_revenue: float = 7500.0, operating_mode: str = "profit_mode") -> str:
    pipeline = _build_pipeline(data_dir, dispatch_revenue, operating_mode)
    project_report = build_project_report(
        pipeline["validation"],
        pipeline["health"],
        pipeline["degradation"],
        pipeline["dispatch"],
        battery_config=dict(pipeline["battery_config"]),
        sensitivity_analysis=pipeline["sensitivity"],
    )
    return render_html_report(project_report)
