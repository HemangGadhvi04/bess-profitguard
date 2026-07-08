from pathlib import Path
import shutil

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.data_generator import SampleDataConfig, generate_sample_data


client = TestClient(app)


def reset_relative_dir(relative_path: str) -> Path:
    path = Path(relative_path)
    if path.exists():
        shutil.rmtree(path)
    return path


def test_api_status() -> None:
    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_is_served() -> None:
    response = client.get("/dashboard/")

    assert response.status_code == 200
    assert "BESS ProfitGuard Dashboard" in response.text
    assert "Upload CSV Session" in response.text
    assert "uploadBessTelemetry" in response.text
    assert "socChart" in response.text
    assert "powerChart" in response.text
    assert "gridChart" in response.text
    assert "/dashboard/app.js" in response.text
    assert "/dashboard/styles.css" in response.text


def test_api_pipeline_endpoints(tmp_path: Path) -> None:
    data_dir = "runs/test-api-pipeline"
    reset_relative_dir(data_dir)
    sample_response = client.post("/api/sample-data", json={"output_dir": data_dir, "days": 2, "seed": 61})
    assert sample_response.status_code == 200
    assert "sample_bess_telemetry" in sample_response.json()["files"]

    validation_response = client.get("/api/validation", params={"data_dir": data_dir})
    assert validation_response.status_code == 200
    assert validation_response.json()["reports"]

    health_response = client.get("/api/battery-health", params={"data_dir": data_dir})
    assert health_response.status_code == 200
    assert "estimated_soh_percent" in health_response.json()

    degradation_response = client.post("/api/degradation-cost", json={"data_dir": data_dir, "dispatch_revenue": 7500})
    assert degradation_response.status_code == 200
    assert "estimated_degradation_cost" in degradation_response.json()

    dispatch_response = client.post("/api/dispatch", json={"data_dir": data_dir, "dispatch_revenue": 7500})
    assert dispatch_response.status_code == 200
    assert "degradation_aware" in dispatch_response.json()

    report_path = "reports/test-api-report.html"
    Path(report_path).unlink(missing_ok=True)
    report_response = client.post(
        "/api/report",
        json={"data_dir": data_dir, "output_path": report_path, "dispatch_revenue": 7500},
    )
    assert report_response.status_code == 200
    assert Path(report_path).exists()


def test_api_html_report(tmp_path: Path) -> None:
    data_dir = "runs/test-api-html-report"
    reset_relative_dir(data_dir)
    client.post("/api/sample-data", json={"output_dir": data_dir, "days": 2, "seed": 62})

    response = client.get("/api/report/html", params={"data_dir": data_dir})

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "BESS ProfitGuard Dispatch Audit" in response.text


def test_api_session_upload_flow(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    generate_sample_data(source_dir, SampleDataConfig(days=2, seed=63))
    base_dir = "runs/test-api-upload"
    reset_relative_dir(base_dir)

    create_response = client.post("/api/sessions", json={"base_dir": str(base_dir)})
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]
    data_dir = create_response.json()["data_dir"]

    upload_map = {
        "bess_telemetry": source_dir / "sample_bess_telemetry.csv",
        "site_load": source_dir / "sample_site_load.csv",
        "pv_generation": source_dir / "sample_pv_generation.csv",
        "tariff": source_dir / "sample_tariff.csv",
        "ev_sessions": source_dir / "sample_ev_sessions.csv",
        "battery_config": source_dir / "sample_battery_config.csv",
    }
    for file_type, path in upload_map.items():
        with path.open("rb") as handle:
            response = client.post(
                f"/api/sessions/{session_id}/upload",
                data={"file_type": file_type, "base_dir": str(base_dir)},
                files={"file": (path.name, handle, "text/csv")},
            )
        assert response.status_code == 200
        assert response.json()["file_type"] == file_type

    files_response = client.get(f"/api/sessions/{session_id}/files", params={"base_dir": str(base_dir)})
    assert files_response.status_code == 200
    assert files_response.json()["missing"] == []

    validation_response = client.get("/api/validation", params={"data_dir": data_dir})
    assert validation_response.status_code == 200
    assert all(report["passed"] for report in validation_response.json()["reports"])

    dispatch_response = client.post("/api/dispatch", json={"data_dir": data_dir, "dispatch_revenue": 7500})
    assert dispatch_response.status_code == 200
    assert dispatch_response.json()["degradation_aware"]["status"] == "optimal"


def test_api_rejects_path_traversal_and_extra_fields() -> None:
    bad_path_response = client.post("/api/sample-data", json={"output_dir": "../secrets", "days": 2, "seed": 1})
    assert bad_path_response.status_code == 400

    extra_field_response = client.post(
        "/api/degradation-cost",
        json={"data_dir": "data", "dispatch_revenue": 7500, "unexpected": "nope"},
    )
    assert extra_field_response.status_code == 422
    assert extra_field_response.json() == {"error": "Invalid request"}


def test_security_headers_are_present() -> None:
    response = client.get("/api/status")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
