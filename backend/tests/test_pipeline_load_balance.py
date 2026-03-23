"""Tests for pipeline load-balance metrics and ranking."""

from services.optimization_pipeline_service import (
    PipelineConfig,
    _report_metrics_from_validation,
    calculate_pipeline_candidate_score,
    rank_pipeline_candidate,
)
from services.workspace_options import sanitize_workspace_optimization_options
from optimizer_v6 import normalize_time_window_limits


def _empty_day() -> dict:
    return {
        "schedule": [],
        "stats": {
            "total_buses": 0,
            "total_routes": 0,
            "total_entries": 0,
            "total_exits": 0,
            "avg_routes_per_bus": 0,
        },
    }


def test_pipeline_config_accepts_balance_fields():
    cfg = PipelineConfig.from_dict(
        {
            "auto_start": True,
            "objective": "min_buses_viability",
            "balance_load": True,
            "load_balance_hard_spread_limit": 3,
            "load_balance_target_band": 2,
        }
    )
    assert cfg.balance_load is True
    assert cfg.load_balance_hard_spread_limit == 3
    assert cfg.load_balance_target_band == 2


def test_pipeline_config_clamps_target_band_to_spread_limit():
    cfg = PipelineConfig.from_dict(
        {
            "balance_load": True,
            "load_balance_hard_spread_limit": 2,
            "load_balance_target_band": 5,
        }
    )
    assert cfg.load_balance_hard_spread_limit == 2
    assert cfg.load_balance_target_band == 2


def test_workspace_options_keep_solver_and_objective_preferences():
    sanitized = sanitize_workspace_optimization_options(
        {
            "objective": "min_deadhead",
            "preferred_solver": "cp_sat",
            "enable_greedy_warm_start": False,
            "time_limit_seconds": 45,
        }
    )
    assert sanitized["objective"] == "min_deadhead"
    assert sanitized["preferred_solver"] == "cp_sat"
    assert sanitized["enable_greedy_warm_start"] is False
    assert sanitized["time_limit_seconds"] == 45


def test_workspace_options_deduplicate_and_clamp_windows():
    sanitized = sanitize_workspace_optimization_options(
        {
            "load_balance_hard_spread_limit": 2,
            "load_balance_target_band": 4,
            "route_load_constraints": [
                {"start_time": "07:30", "end_time": "09:30", "max_routes": 4, "enabled": True},
                {"start_time": "07:30", "end_time": "09:30", "max_routes": 2, "enabled": True, "label": "Pico manana"},
                {"start_time": "bad", "end_time": "09:30", "max_routes": 3, "enabled": True},
            ],
        }
    )
    assert sanitized["load_balance_target_band"] == 2
    assert len(sanitized["route_load_constraints"]) == 1
    assert sanitized["route_load_constraints"][0]["max_routes"] == 2
    assert sanitized["route_load_constraints"][0]["label"] == "07:30-09:30"


def test_optimizer_window_normalization_keeps_stricter_duplicate():
    limits = normalize_time_window_limits(
        [
            {"start_time": "07:30", "end_time": "09:30", "max_routes": 4, "enabled": True},
            {"start_time": "07:30", "end_time": "09:30", "max_routes": 2, "enabled": True, "label": "Pico manana"},
        ]
    )
    assert len(limits) == 1
    assert limits[0].max_routes == 2
    assert limits[0].label == "07:30-09:30"


def test_report_metrics_include_load_fields():
    schedule_by_day = {day: _empty_day() for day in ["L", "M", "Mc", "X", "V"]}
    schedule_by_day["L"]["schedule"] = [
        {"bus_id": "B001", "items": [{"route_id": "R1"}] * 4},
        {"bus_id": "B002", "items": [{"route_id": "R2"}]},
    ]
    schedule_by_day["M"]["schedule"] = [
        {"bus_id": "B003", "items": [{"route_id": "R3"}] * 3},
        {"bus_id": "B004", "items": [{"route_id": "R4"}] * 2},
    ]
    report = {
        "summary": {
            "total_buses": 4,
            "feasible_buses": 4,
            "incidents_error": 0,
            "incidents_warning": 0,
        }
    }

    metrics = _report_metrics_from_validation(report, schedule_by_day)
    assert "median_routes_per_bus" in metrics
    assert "min_routes_per_bus" in metrics
    assert "max_routes_per_bus" in metrics
    assert "load_spread_routes" in metrics
    assert "load_abs_dev_sum" in metrics
    assert "load_balanced" in metrics
    assert metrics["load_spread_routes"] == 3
    assert metrics["min_routes_per_bus"] == 1
    assert metrics["max_routes_per_bus"] == 4
    assert metrics["median_routes_per_bus"] == 2.5


def test_candidate_rank_prefers_lower_spread_when_buses_equal():
    a = {
        "split_count": 0,
        "infeasible_buses": 0,
        "best_buses": 40,
        "load_spread_routes": 6,
        "load_abs_dev_sum": 28.0,
        "error_issues": 0,
        "warning_issues": 0,
        "avg_deadhead": 10.0,
        "avg_efficiency": 80.0,
    }
    b = {
        "split_count": 0,
        "infeasible_buses": 0,
        "best_buses": 40,
        "load_spread_routes": 2,
        "load_abs_dev_sum": 9.0,
        "error_issues": 0,
        "warning_issues": 0,
        "avg_deadhead": 12.0,
        "avg_efficiency": 79.0,
    }
    assert rank_pipeline_candidate(b) < rank_pipeline_candidate(a)
    assert calculate_pipeline_candidate_score(b) < calculate_pipeline_candidate_score(a)
