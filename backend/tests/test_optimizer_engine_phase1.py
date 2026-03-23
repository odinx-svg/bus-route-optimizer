"""Contract tests for the new pluggable optimizer engine phase 1."""

from __future__ import annotations

from datetime import time

import optimizer
from models import BusSchedule, Route, Stop
from optimizer import OptimizerConfig, OptimizerEngine, SolverResult, build_greedy_schedule
from optimizer.solver_cpsat import CpSatOptimizerSolver
from services.optimization_pipeline_service import PipelineConfig, _optimize_by_day_v6


def _route(
    route_id: str,
    *,
    route_type: str,
    event_time: time,
    duration_minutes: int,
    capacity_needed: int = 20,
    start_lat: float = 42.2400,
    start_lon: float = -8.7200,
    end_lat: float = 42.2500,
    end_lon: float = -8.7300,
    days: list[str] | None = None,
) -> Route:
    return Route(
        id=route_id,
        name=route_id,
        stops=[
            Stop(
                name=f"{route_id}-start",
                lat=start_lat,
                lon=start_lon,
                order=1,
                time_from_start=0,
                passengers=max(1, capacity_needed // 2),
            ),
            Stop(
                name=f"{route_id}-end",
                lat=end_lat,
                lon=end_lon,
                order=2,
                time_from_start=duration_minutes,
                passengers=0,
                is_school=True,
            ),
        ],
        school_id="SCH001",
        school_name="Colegio Test",
        arrival_time=event_time if route_type == "entry" else None,
        departure_time=event_time if route_type == "exit" else None,
        capacity_needed=capacity_needed,
        contract_id="CNT001",
        type=route_type,
        days=days or ["L"],
    )


def _to_minutes(value: time) -> int:
    return (value.hour * 60) + value.minute


def test_optimizer_config_normalizes_aliases_and_clamps_target_band():
    cfg = OptimizerConfig.from_dict(
        {
            "objective": "min_buses_viability_hybrid",
            "preferred_solver": "CP_SAT",
            "load_balance_hard_spread_limit": 2,
            "load_balance_target_band": 9,
        }
    )

    assert cfg.objective_mode == "min_buses"
    assert cfg.preferred_solver == "cp_sat"
    assert cfg.load_balance_hard_spread_limit == 2
    assert cfg.load_balance_target_band == 2
    assert cfg.objective_weights["buses"] == 1000.0


def test_optimizer_config_defaults_to_auto_solver():
    cfg = OptimizerConfig.from_dict({"objective": "min_km"})

    assert cfg.preferred_solver == "auto"


def test_pipeline_config_accepts_solver_preferences_for_new_engine():
    cfg = PipelineConfig.from_dict(
        {
            "objective": "min_km",
            "preferred_solver": "cp_sat",
            "enable_greedy_warm_start": False,
            "time_limit_seconds": 45,
        }
    )

    assert cfg.objective == "min_km"
    assert cfg.preferred_solver == "cp_sat"
    assert cfg.enable_greedy_warm_start is False
    assert cfg.time_limit_seconds == 45


def test_build_greedy_schedule_assigns_all_routes_once_and_without_overlap():
    routes = [
        _route("R001", route_type="entry", event_time=time(8, 0), duration_minutes=20),
        _route("R002", route_type="entry", event_time=time(8, 30), duration_minutes=20),
        _route("R003", route_type="entry", event_time=time(8, 15), duration_minutes=20),
    ]

    schedule = build_greedy_schedule(routes)

    assigned_route_ids = {
        item.route_id
        for bus in schedule
        for item in bus.items
    }
    assert len(schedule) == 2
    assert assigned_route_ids == {"R001", "R002", "R003"}

    for bus in schedule:
        ordered_items = sorted(bus.items, key=lambda item: _to_minutes(item.start_time))
        for current, nxt in zip(ordered_items, ordered_items[1:]):
            assert _to_minutes(current.end_time) <= _to_minutes(nxt.start_time)


def test_optimizer_engine_builds_greedy_seed_before_solver_call():
    routes = [
        _route("R010", route_type="entry", event_time=time(8, 0), duration_minutes=20),
        _route("R011", route_type="exit", event_time=time(15, 0), duration_minutes=25),
    ]
    captured: dict[str, object] = {}

    class FakeSolver:
        name = "fake"

        def optimize(self, routes, config, progress_callback=None, initial_schedule=None):
            captured["config"] = config
            captured["initial_schedule"] = initial_schedule
            return SolverResult(
                schedule=initial_schedule or [],
                diagnostics={"solver_name": "fake"},
                solver_name="fake",
                initial_schedule=initial_schedule,
            )

    engine = OptimizerEngine()
    engine._pulp_solver = FakeSolver()

    result = engine.optimize(
        routes,
        config=OptimizerConfig(enable_greedy_warm_start=True, preferred_solver="pulp_v6"),
    )

    assert captured["initial_schedule"] is not None
    assert isinstance(result.schedule, list)
    assert result.diagnostics["greedy_seed"]["route_count"] == 2
    assert result.diagnostics["greedy_seed"]["bus_count"] == len(result.initial_schedule or [])
    assert result.diagnostics["requested_solver"] == "pulp_v6"
    assert result.diagnostics["selected_solver"] == "fake"
    assert result.diagnostics["solver_fallback_used"] is False


def test_cp_sat_solver_builds_schedule_for_simple_routes():
    routes = [
        _route("R100", route_type="entry", event_time=time(8, 0), duration_minutes=20),
        _route("R101", route_type="entry", event_time=time(8, 30), duration_minutes=20),
        _route("R102", route_type="exit", event_time=time(15, 0), duration_minutes=25),
    ]

    solver = CpSatOptimizerSolver()
    if not solver.is_available:
        return

    result = solver.optimize(
        routes,
        config=OptimizerConfig(preferred_solver="cp_sat", time_limit_seconds=5),
    )

    assigned_route_ids = {item.route_id for bus in result.schedule for item in bus.items}
    assert assigned_route_ids == {"R100", "R101", "R102"}
    assert result.solver_name == "cp_sat"
    assert result.diagnostics["solver_name"] == "cp_sat"
    assert result.diagnostics["best_buses"] >= 1


def test_optimizer_engine_selects_cp_sat_when_available():
    routes = [_route("R120", route_type="entry", event_time=time(8, 0), duration_minutes=20)]
    captured: dict[str, object] = {}

    class FakeCpSatSolver:
        name = "cp_sat"
        is_available = True

        def optimize(self, routes, config, progress_callback=None, initial_schedule=None):
            captured["solver"] = "cp_sat"
            return SolverResult(
                schedule=[],
                diagnostics={"solver_name": "cp_sat"},
                solver_name="cp_sat",
                initial_schedule=initial_schedule,
            )

    engine = OptimizerEngine()
    engine._cp_sat_solver = FakeCpSatSolver()

    result = engine.optimize(routes, config=OptimizerConfig(preferred_solver="cp_sat"))

    assert captured["solver"] == "cp_sat"
    assert result.diagnostics["selected_solver"] == "cp_sat"
    assert result.diagnostics["solver_fallback_used"] is False


def test_optimizer_engine_auto_falls_back_to_pulp_while_cp_sat_is_experimental():
    routes = [_route("R130", route_type="entry", event_time=time(8, 0), duration_minutes=20)]
    captured: dict[str, object] = {}

    class FakePulpSolver:
        name = "pulp_v6"

        def optimize(self, routes, config, progress_callback=None, initial_schedule=None):
            captured["solver"] = "pulp_v6"
            return SolverResult(
                schedule=[],
                diagnostics={"solver_name": "pulp_v6"},
                solver_name="pulp_v6",
                initial_schedule=initial_schedule,
            )

    class FakeCpSatSolver:
        name = "cp_sat"
        is_available = True

        def optimize(self, routes, config, progress_callback=None, initial_schedule=None):
            raise AssertionError("auto should not pick cp_sat while it is experimental")

    engine = OptimizerEngine()
    engine._pulp_solver = FakePulpSolver()
    engine._cp_sat_solver = FakeCpSatSolver()

    result = engine.optimize(
        routes,
        config=OptimizerConfig(preferred_solver="auto", objective_mode="min_deadhead"),
    )

    assert captured["solver"] == "pulp_v6"
    assert result.diagnostics["selected_solver"] == "pulp_v6"
    assert result.diagnostics["solver_selection_reason"] == "auto:fallback_cp_sat_experimental"
    assert result.diagnostics["solver_selection"]["decision_mode"] == "auto"
    assert result.diagnostics["solver_selection_label"] == "CP-SAT aun experimental"


def test_optimizer_engine_auto_falls_back_to_pulp_when_route_rules_exist():
    routes = [_route("R131", route_type="entry", event_time=time(8, 0), duration_minutes=20)]
    captured: dict[str, object] = {}

    class FakePulpSolver:
        name = "pulp_v6"

        def optimize(self, routes, config, progress_callback=None, initial_schedule=None):
            captured["solver"] = "pulp_v6"
            return SolverResult(
                schedule=[],
                diagnostics={"solver_name": "pulp_v6"},
                solver_name="pulp_v6",
                initial_schedule=initial_schedule,
            )

    class FakeCpSatSolver:
        name = "cp_sat"
        is_available = True

        def optimize(self, *args, **kwargs):
            raise AssertionError("cp_sat should not be selected")

    engine = OptimizerEngine()
    engine._pulp_solver = FakePulpSolver()
    engine._cp_sat_solver = FakeCpSatSolver()

    result = engine.optimize(
        routes,
        config=OptimizerConfig(
            preferred_solver="auto",
            objective_mode="min_deadhead",
            route_load_constraints=[{"start_time": "07:30", "end_time": "09:30", "max_routes": 2}],
        ),
    )

    assert captured["solver"] == "pulp_v6"
    assert result.diagnostics["selected_solver"] == "pulp_v6"
    assert result.diagnostics["solver_selection_reason"] == "auto:fallback_cp_sat_experimental"
    assert result.diagnostics["solver_selection"]["supports_route_load_constraints"] is True


def test_optimize_by_day_v6_forwards_pipeline_objective_to_optimizer_engine(monkeypatch):
    route = _route("R200", route_type="entry", event_time=time(8, 10), duration_minutes=20, days=["L"])
    captured: list[tuple[str, str, bool, bool, int | None]] = []

    class FakeEngine:
        def __init__(self) -> None:
            self._last = {"solver_status": "optimal"}

        def optimize(self, routes, config=None, progress_callback=None):
            captured.append(
                (
                    config.objective_mode,
                    config.preferred_solver,
                    bool(config.use_ml_assignment),
                    bool(config.enable_greedy_warm_start),
                    config.time_limit_seconds,
                )
            )
            return SolverResult(
                schedule=[BusSchedule(bus_id="B001", items=[])],
                diagnostics=dict(self._last),
                solver_name="fake",
                initial_schedule=None,
            )

        def get_last_diagnostics(self):
            return dict(self._last)

    monkeypatch.setattr(optimizer, "OptimizerEngine", FakeEngine)

    by_day, diagnostics = _optimize_by_day_v6(
        [route],
        objective="min_km",
        preferred_solver="cp_sat",
        use_ml_assignment=False,
        enable_greedy_warm_start=False,
        time_limit_seconds=90,
    )

    assert captured == [("min_km", "cp_sat", False, False, 90)]
    assert "L" in by_day
    assert diagnostics["L"]["solver_status"] == "optimal"
