"""
API tests for ML assignment toggle and A/B comparison endpoint.
"""

from datetime import time
from typing import Any, Dict, List

from fastapi.testclient import TestClient

from models import BusSchedule, ScheduleItem, Stop


def _make_schedule(bus_count: int) -> List[BusSchedule]:
    schedules: List[BusSchedule] = []
    for idx in range(bus_count):
        item = ScheduleItem(
            route_id=f"R{idx:03d}",
            start_time=time(8, 0),
            end_time=time(8, 20),
            type="entry",
            school_name="School Test",
            stops=[
                Stop(
                    name="Stop",
                    lat=42.24,
                    lon=-8.72,
                    order=1,
                    time_from_start=0,
                    passengers=5,
                    is_school=False,
                ),
                Stop(
                    name="School",
                    lat=42.25,
                    lon=-8.73,
                    order=2,
                    time_from_start=20,
                    passengers=0,
                    is_school=True,
                ),
            ],
            contract_id="CNT",
            original_start_time=time(8, 20),
            time_shift_minutes=0,
            deadhead_minutes=0,
        )
        schedules.append(BusSchedule(bus_id=f"B{idx + 1:03d}", items=[item]))
    return schedules


def test_optimize_v6_forwards_use_ml_assignment_flag(monkeypatch):
    from main import app
    import optimizer_v6

    captured: Dict[str, Any] = {"use_ml_assignment": None}

    def fake_optimize_v6(routes, progress_callback=None, use_ml_assignment=True):
        captured["use_ml_assignment"] = bool(use_ml_assignment)
        return []

    monkeypatch.setattr(optimizer_v6, "optimize_v6", fake_optimize_v6)

    client = TestClient(app)
    response = client.post("/optimize-v6?use_ml_assignment=false", json=[])

    assert response.status_code == 200
    data = response.json()
    assert captured["use_ml_assignment"] is False
    assert data["optimization_options"]["use_ml_assignment"] is False


def test_optimize_v6_ab_returns_deltas_and_recommendation(monkeypatch):
    from main import app
    import optimizer_v6

    def fake_optimize_v6(routes, progress_callback=None, use_ml_assignment=True):
        if use_ml_assignment:
            return _make_schedule(1)
        return _make_schedule(2)

    monkeypatch.setattr(optimizer_v6, "optimize_v6", fake_optimize_v6)

    client = TestClient(app)
    response = client.post("/optimize-v6-ab", json=[])

    assert response.status_code == 200
    data = response.json()
    assert data["comparison"]["ml_off"]["stats"]["total_buses"] == 2
    assert data["comparison"]["ml_on"]["stats"]["total_buses"] == 1
    assert data["comparison"]["deltas_ml_on_minus_ml_off"]["total_buses"] == -1
    assert data["recommendation"]["mode"] == "ml_on"
