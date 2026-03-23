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


def _make_route_payload(route_id: str = "R001", days: List[str] | None = None) -> Dict[str, Any]:
    return {
        "id": route_id,
        "name": route_id,
        "stops": [
            {
                "name": "Stop",
                "lat": 42.24,
                "lon": -8.72,
                "order": 1,
                "time_from_start": 0,
                "passengers": 5,
                "is_school": False,
            },
            {
                "name": "School",
                "lat": 42.25,
                "lon": -8.73,
                "order": 2,
                "time_from_start": 20,
                "passengers": 0,
                "is_school": True,
            },
        ],
        "school_id": "SCH001",
        "school_name": "School Test",
        "arrival_time": "08:20:00",
        "departure_time": None,
        "capacity_needed": 20,
        "contract_id": "CNT",
        "type": "entry",
        "days": list(days or ["L"]),
    }


def test_optimize_v6_forwards_use_ml_assignment_flag(monkeypatch):
    from main import app

    captured: Dict[str, Any] = {}

    def fake_run_optimizer_engine_once(
        routes,
        *,
        objective,
        preferred_solver,
        use_ml_assignment,
        balance_load,
        load_balance_hard_spread_limit,
        load_balance_target_band,
        enable_greedy_warm_start,
        time_limit_seconds,
    ):
        captured["objective"] = objective
        captured["preferred_solver"] = preferred_solver
        captured["use_ml_assignment"] = bool(use_ml_assignment)
        captured["balance_load"] = bool(balance_load)
        captured["enable_greedy_warm_start"] = bool(enable_greedy_warm_start)
        captured["time_limit_seconds"] = time_limit_seconds
        return _make_schedule(1), {"selected_solver": preferred_solver, "solver_status": "optimal"}

    monkeypatch.setattr("main._run_optimizer_engine_once", fake_run_optimizer_engine_once)

    client = TestClient(app)
    response = client.post(
        "/optimize-v6?objective=min_km&preferred_solver=cp_sat&use_ml_assignment=false"
        "&enable_greedy_warm_start=false&time_limit_seconds=12",
        json=[_make_route_payload()],
    )

    assert response.status_code == 200
    data = response.json()
    assert captured["objective"] == "min_km"
    assert captured["preferred_solver"] == "cp_sat"
    assert captured["use_ml_assignment"] is False
    assert captured["balance_load"] is True
    assert captured["enable_greedy_warm_start"] is False
    assert captured["time_limit_seconds"] == 12
    assert data["optimization_options"]["use_ml_assignment"] is False
    assert data["optimization_options"]["preferred_solver"] == "cp_sat"
    assert data["optimization_options"]["objective"] == "min_km"
    assert data["optimizer_diagnostics"]["selected_solver"] == "cp_sat"


def test_optimize_v6_by_day_forwards_solver_preferences(monkeypatch):
    from main import app

    captured_calls: List[Dict[str, Any]] = []

    def fake_run_optimizer_engine_once(
        routes,
        *,
        objective,
        preferred_solver,
        use_ml_assignment,
        balance_load,
        load_balance_hard_spread_limit,
        load_balance_target_band,
        enable_greedy_warm_start,
        time_limit_seconds,
    ):
        captured_calls.append(
            {
                "route_count": len(routes),
                "objective": objective,
                "preferred_solver": preferred_solver,
                "use_ml_assignment": bool(use_ml_assignment),
                "enable_greedy_warm_start": bool(enable_greedy_warm_start),
                "time_limit_seconds": time_limit_seconds,
            }
        )
        return _make_schedule(1), {"selected_solver": preferred_solver, "solver_status": "optimal"}

    monkeypatch.setattr("main._run_optimizer_engine_once", fake_run_optimizer_engine_once)

    client = TestClient(app)
    response = client.post(
        "/optimize-v6-by-day?objective=min_deadhead&preferred_solver=cp_sat"
        "&enable_greedy_warm_start=false&time_limit_seconds=9",
        json=[
            _make_route_payload("R001", ["L", "M"]),
            _make_route_payload("R002", ["L"]),
        ],
    )

    assert response.status_code == 200
    data = response.json()
    assert len(captured_calls) == 2
    assert captured_calls[0]["objective"] == "min_deadhead"
    assert captured_calls[0]["preferred_solver"] == "cp_sat"
    assert captured_calls[0]["enable_greedy_warm_start"] is False
    assert captured_calls[0]["time_limit_seconds"] == 9
    assert data["L"]["optimization_options"]["preferred_solver"] == "cp_sat"
    assert data["L"]["optimizer_diagnostics"]["selected_solver"] == "cp_sat"
    assert data["V"]["stats"]["total_buses"] == 0


def test_optimize_v6_ab_returns_deltas_and_recommendation(monkeypatch):
    from main import app
    import optimizer_v6

    def fake_optimize_v6(
        routes,
        progress_callback=None,
        use_ml_assignment=True,
        balance_load=True,
        load_balance_hard_spread_limit=2,
        load_balance_target_band=1,
    ):
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
