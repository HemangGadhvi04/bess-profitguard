from __future__ import annotations

import json
from pathlib import Path

from backend.app.services.telemetry_validator import validate_generated_dataset


if __name__ == "__main__":
    reports = validate_generated_dataset(Path("data"))
    payload = [report.to_dict() for report in reports]
    print(json.dumps(payload, indent=2))
    if any(not report.passed for report in reports):
        raise SystemExit(1)
