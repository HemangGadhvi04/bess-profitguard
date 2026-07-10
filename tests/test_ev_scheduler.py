import pandas as pd

from backend.app.services.ev_scheduler import summarize_ev_readiness


def test_ev_readiness_is_100_percent_when_all_sessions_are_met() -> None:
    sessions = pd.DataFrame(
        [
            {"session_id": "EV-1", "priority_level": 1},
            {"session_id": "EV-2", "priority_level": 3},
        ]
    )

    summary = summarize_ev_readiness(sessions, [0.0, 0.0])

    assert summary.readiness_percent == 100.0
    assert summary.priority_readiness_percent == 100.0
    assert summary.unmet_energy_kwh == 0.0


def test_ev_readiness_tracks_priority_failures() -> None:
    sessions = pd.DataFrame(
        [
            {"session_id": "EV-1", "priority_level": 1},
            {"session_id": "EV-2", "priority_level": 3},
        ]
    )

    summary = summarize_ev_readiness(sessions, [5.0, 0.0])

    assert summary.readiness_percent == 50.0
    assert summary.priority_readiness_percent == 0.0
    assert summary.unmet_energy_kwh == 5.0
