"""
Orquestador de pipeline de optimizaciÃ³n por dÃ­a con validaciÃ³n OSRM.

Pipeline:
1) ingest
2) baseline_optimize (V6)
3) osrm_validate
4) reoptimize_iter_n (V6+LNS or Hybrid QUBO refine)
5) osrm_validate_iter_n
6) select_best
7) completed
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime, time
from statistics import median
from time import time as now_seconds
from typing import Any, Callable, Dict, List, Optional, Tuple

from models import Route, BusSchedule, ScheduleItem
try:
    from services.fleet_assignment import assign_fleet_profiles_to_schedule_by_day
except ImportError:
    from backend.services.fleet_assignment import assign_fleet_profiles_to_schedule_by_day

DAY_NAMES: Dict[str, str] = {
    "L": "Lunes",
    "M": "Martes",
    "Mc": "MiÃ©rcoles",
    "X": "Jueves",
    "V": "Viernes",
}
ALL_DAYS: List[str] = ["L", "M", "Mc", "X", "V"]
DayTraceCallback = Optional[Callable[[str, str, int, str, Optional[Dict[str, Any]]], None]]
logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    """Read an integer from environment, falling back to *default*."""
    raw = os.environ.get(name, "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    return default


# Desktop-tunable defaults (overridable via env vars set by the launcher).
_DEFAULT_MAX_DURATION_SEC = _env_int("TUTTI_PIPELINE_MAX_DURATION_SEC", 300)
_DEFAULT_MAX_ITERATIONS = _env_int("TUTTI_PIPELINE_MAX_ITERATIONS", 2)


@dataclass
class PipelineConfig:
    auto_start: bool = True
    objective: str = "min_buses_viability"
    max_duration_sec: int = _DEFAULT_MAX_DURATION_SEC
    max_iterations: int = _DEFAULT_MAX_ITERATIONS
    use_ml_assignment: bool = True
    invalid_rows_dropped: int = 0
    balance_load: bool = True
    load_balance_hard_spread_limit: int = 2
    load_balance_target_band: int = 1

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "PipelineConfig":
        if not isinstance(data, dict):
            return cls()
        return cls(
            auto_start=bool(data.get("auto_start", True)),
            objective=str(data.get("objective", "min_buses_viability")),
            max_duration_sec=max(30, int(data.get("max_duration_sec", _DEFAULT_MAX_DURATION_SEC))),
            max_iterations=int(data.get("max_iterations", _DEFAULT_MAX_ITERATIONS)),
            use_ml_assignment=bool(data.get("use_ml_assignment", True)),
            invalid_rows_dropped=max(0, int(data.get("invalid_rows_dropped", 0))),
            balance_load=bool(data.get("balance_load", True)),
            load_balance_hard_spread_limit=max(1, int(data.get("load_balance_hard_spread_limit", 2))),
            load_balance_target_band=max(0, int(data.get("load_balance_target_band", 1))),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "auto_start": self.auto_start,
            "objective": self.objective,
            "max_duration_sec": self.max_duration_sec,
            "max_iterations": self.max_iterations,
            "use_ml_assignment": self.use_ml_assignment,
            "invalid_rows_dropped": self.invalid_rows_dropped,
            "balance_load": self.balance_load,
            "load_balance_hard_spread_limit": self.load_balance_hard_spread_limit,
            "load_balance_target_band": self.load_balance_target_band,
        }


def calculate_pipeline_candidate_score(metrics: Dict[str, Any]) -> float:
    """
    Score final (menor es mejor):
    score = 1000*infeasible_buses + 100*error_issues + 20*warning_issues
            + 10*best_buses + 5000*split_count - avg_efficiency
            + 25*load_spread_routes + 2*load_abs_dev_sum
    """
    infeasible_buses = int(metrics.get("infeasible_buses", 0))
    error_issues = int(metrics.get("error_issues", 0))
    warning_issues = int(metrics.get("warning_issues", 0))
    best_buses = int(metrics.get("best_buses", metrics.get("total_buses", 0)))
    split_count = int(metrics.get("split_count", 0))
    avg_efficiency = float(metrics.get("avg_efficiency", 0.0))
    load_spread_routes = int(metrics.get("load_spread_routes", 0))
    load_abs_dev_sum = float(metrics.get("load_abs_dev_sum", 0.0))
    return (
        (1000 * infeasible_buses)
        + (100 * error_issues)
        + (20 * warning_issues)
        + (10 * best_buses)
        + (5000 * split_count)
        - avg_efficiency
        + (25 * load_spread_routes)
        + (2 * load_abs_dev_sum)
    )


def rank_pipeline_candidate(metrics: Dict[str, Any]) -> Tuple[Any, ...]:
    """Lexicographic ranking for candidate selection (smaller is better)."""
    return (
        1 if int(metrics.get("split_count", 0)) > 0 else 0,
        int(metrics.get("infeasible_buses", 0)),
        int(metrics.get("best_buses", metrics.get("total_buses", 0))),
        int(metrics.get("load_spread_routes", 0)),
        float(metrics.get("load_abs_dev_sum", 0.0)),
        int(metrics.get("error_issues", 0)),
        float(metrics.get("avg_deadhead", 0.0)),
        int(metrics.get("warning_issues", 0)),
        -float(metrics.get("avg_efficiency", 0.0)),
    )


def _safe_emit_progress(
    progress_callback: Optional[Callable[..., None]],
    phase: str,
    progress: int,
    message: str,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    if not progress_callback:
        return
    payload = extra or {}
    try:
        progress_callback(phase, progress, message, payload)
    except TypeError:
        # Compatibilidad con callbacks antiguos de 3 argumentos.
        progress_callback(phase, progress, message)


def _calculate_stats(schedule: List[BusSchedule]) -> Dict[str, Any]:
    if not schedule:
        return {
            "total_buses": 0,
            "total_routes": 0,
            "total_entries": 0,
            "total_exits": 0,
            "max_entries_per_bus": 0,
            "max_exits_per_bus": 0,
            "buses_with_both": 0,
            "avg_routes_per_bus": 0,
            "total_early_shift_minutes": 0,
            "median_routes_per_bus": 0.0,
            "min_routes_per_bus": 0,
            "max_routes_per_bus": 0,
            "load_spread_routes": 0,
            "load_abs_dev_sum": 0.0,
            "load_balanced": True,
        }

    total_routes = sum(len(bus.items) for bus in schedule)
    entry_counts = [sum(1 for i in bus.items if i.type == "entry") for bus in schedule]
    exit_counts = [sum(1 for i in bus.items if i.type == "exit") for bus in schedule]
    max_entries = max(entry_counts) if entry_counts else 0
    max_exits = max(exit_counts) if exit_counts else 0
    buses_with_both = sum(1 for i, e in enumerate(entry_counts) if e > 0 and exit_counts[i] > 0)
    total_early_shift = sum(
        item.time_shift_minutes for bus in schedule for item in bus.items if item.time_shift_minutes > 0
    )
    route_counts = sorted(len(bus.items) for bus in schedule if bus.items)
    med_routes = float(median(route_counts)) if route_counts else 0.0
    min_routes = int(route_counts[0]) if route_counts else 0
    max_routes = int(route_counts[-1]) if route_counts else 0
    spread = int(max_routes - min_routes) if route_counts else 0
    abs_dev_sum = float(sum(abs(float(v) - med_routes) for v in route_counts)) if route_counts else 0.0

    return {
        "total_buses": len(schedule),
        "total_routes": total_routes,
        "total_entries": sum(entry_counts),
        "total_exits": sum(exit_counts),
        "max_entries_per_bus": max_entries,
        "max_exits_per_bus": max_exits,
        "buses_with_both": buses_with_both,
        "avg_routes_per_bus": round(total_routes / len(schedule), 1) if schedule else 0,
        "total_early_shift_minutes": total_early_shift,
        "median_routes_per_bus": round(med_routes, 2),
        "min_routes_per_bus": min_routes,
        "max_routes_per_bus": max_routes,
        "load_spread_routes": spread,
        "load_abs_dev_sum": round(abs_dev_sum, 2),
        "load_balanced": spread <= 2,
    }


def _extract_item_locations(item: Any) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    stops = getattr(item, "stops", []) or []
    if len(stops) > 0:
        first = stops[0]
        last = stops[-1]
        return (float(first.lat), float(first.lon)), (float(last.lat), float(last.lon))
    return (0.0, 0.0), (0.0, 0.0)


def _time_to_minutes(value: Optional[time], default_minutes: int = 0) -> int:
    if isinstance(value, time):
        return (value.hour * 60) + value.minute
    return int(default_minutes)


def _minutes_to_time(total_minutes: int) -> time:
    normalized = int(total_minutes) % (24 * 60)
    return time(hour=normalized // 60, minute=normalized % 60)


def _route_duration_minutes(route: Route) -> int:
    durations = []
    for stop in route.stops or []:
        try:
            durations.append(int(getattr(stop, "time_from_start", 0) or 0))
        except Exception:
            continue
    return max(5, max(durations) if durations else 30)


def _build_route_per_bus_fallback(day_routes: List[Route]) -> List[BusSchedule]:
    """
    Conservative fail-safe schedule:
    one route per bus, preserving all routes when optimizer crashes.
    """
    ordered = sorted(
        day_routes,
        key=lambda route: (
            _time_to_minutes(route.arrival_time, 23 * 60)
            if route.type == "entry"
            else _time_to_minutes(route.departure_time, 23 * 60),
            str(route.id),
        ),
    )
    fallback: List[BusSchedule] = []
    for idx, route in enumerate(ordered, start=1):
        duration = _route_duration_minutes(route)
        if route.type == "entry":
            end_minutes = _time_to_minutes(route.arrival_time, 8 * 60)
            start_minutes = end_minutes - duration
            start_time = _minutes_to_time(start_minutes)
            end_time = _minutes_to_time(end_minutes)
            original_start = route.arrival_time
        else:
            start_minutes = _time_to_minutes(route.departure_time, 15 * 60)
            end_minutes = start_minutes + duration
            start_time = _minutes_to_time(start_minutes)
            end_time = _minutes_to_time(end_minutes)
            original_start = route.departure_time

        item = ScheduleItem(
            route_id=route.id,
            start_time=start_time,
            end_time=end_time,
            type=route.type,
            original_start_time=original_start,
            time_shift_minutes=0,
            deadhead_minutes=0,
            positioning_minutes=0,
            capacity_needed=int(route.capacity_needed or 0),
            vehicle_capacity_min=route.vehicle_capacity_min,
            vehicle_capacity_max=route.vehicle_capacity_max,
            vehicle_capacity_range=route.vehicle_capacity_range,
            school_name=route.school_name,
            stops=list(route.stops or []),
            contract_id=route.contract_id,
        )
        fallback.append(
            BusSchedule(
                bus_id=f"B{idx:03d}",
                items=[item],
                last_loc=(item.stops[-1].lat, item.stops[-1].lon) if item.stops else None,
                min_required_seats=max(1, int(route.capacity_needed or 1)),
            )
        )
    return fallback


async def _validate_schedule_by_day(schedule_by_day: Dict[str, List[BusSchedule]]) -> Dict[str, Any]:
    """
    Valida todos los buses por dÃ­a usando ManualScheduleValidator.
    """
    try:
        from services.manual_schedule_validator import ManualScheduleValidator, OSRMService
        from models.validation_result import AssignedRoute
    except ImportError:
        from backend.services.manual_schedule_validator import ManualScheduleValidator, OSRMService
        from backend.models.validation_result import AssignedRoute

    validator = ManualScheduleValidator(OSRMService())
    day_reports: List[Dict[str, Any]] = []
    incidents: List[Dict[str, Any]] = []
    max_parallel = max(2, min(12, int(os.cpu_count() or 4)))
    semaphore = asyncio.Semaphore(max_parallel)

    total_buses = 0
    feasible_buses = 0
    buses_with_issues = 0

    async def _validate_bus(day: str, bus: BusSchedule) -> Dict[str, Any]:
        async with semaphore:
            try:
                sorted_items = sorted(
                    bus.items,
                    key=lambda item: ((item.start_time.hour * 60) + item.start_time.minute),
                )
                assigned_routes: List[Any] = []
                for item in sorted_items:
                    start_location, end_location = _extract_item_locations(item)
                    assigned_routes.append(
                        AssignedRoute(
                            id=item.route_id,
                            route_id=item.route_id,
                            start_time=item.start_time,
                            end_time=item.end_time,
                            start_location=start_location,
                            end_location=end_location,
                            type=item.type,
                            school_name=item.school_name,
                        )
                    )

                result = await validator.validate_bus_schedule(assigned_routes)
                issue_dicts = []
                for issue in result.issues:
                    issue_data = issue.dict()
                    issue_data["day"] = day
                    issue_data["bus_id"] = bus.bus_id
                    issue_dicts.append(issue_data)

                return {
                    "bus_id": bus.bus_id,
                    "is_valid": bool(result.is_valid),
                    "issues_count": len(issue_dicts),
                    "issues": issue_dicts,
                    "total_travel_time": round(result.total_travel_time, 1),
                    "efficiency_score": round(result.efficiency_score, 1),
                    "buffer_stats": result.buffer_stats,
                }
            except Exception as exc:
                logger.warning(f"[Validation] Error validating bus {getattr(bus, 'bus_id', 'unknown')}: {exc}")
                fallback_issue = {
                    "day": day,
                    "bus_id": getattr(bus, "bus_id", "unknown"),
                    "severity": "error",
                    "issue_type": "validation_error",
                    "message": f"Validation failed: {type(exc).__name__}",
                }
                return {
                    "bus_id": getattr(bus, "bus_id", "unknown"),
                    "is_valid": False,
                    "issues_count": 1,
                    "issues": [fallback_issue],
                    "total_travel_time": 0.0,
                    "efficiency_score": 0.0,
                    "buffer_stats": {},
                }

    for day in ALL_DAYS:
        buses = schedule_by_day.get(day, [])
        validation_tasks = [asyncio.create_task(_validate_bus(day, bus)) for bus in buses]
        bus_reports: List[Dict[str, Any]] = (
            await asyncio.gather(*validation_tasks) if validation_tasks else []
        )
        day_feasible = 0
        day_with_issues = 0

        for bus_report in bus_reports:
            issue_dicts = bus_report.get("issues", [])
            incidents.extend(issue_dicts)
            if bus_report.get("is_valid"):
                day_feasible += 1
            if issue_dicts:
                day_with_issues += 1

        day_reports.append(
            {
                "day": day,
                "summary": {
                    "total_buses": len(buses),
                    "feasible_buses": day_feasible,
                    "buses_with_issues": day_with_issues,
                    "incidents_total": sum(b["issues_count"] for b in bus_reports),
                },
                "buses": bus_reports,
            }
        )

        total_buses += len(buses)
        feasible_buses += day_feasible
        buses_with_issues += day_with_issues

    error_issues = sum(1 for issue in incidents if issue.get("severity") == "error")
    warning_issues = sum(1 for issue in incidents if issue.get("severity") == "warning")
    info_issues = sum(1 for issue in incidents if issue.get("severity") == "info")

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "summary": {
            "total_buses": total_buses,
            "feasible_buses": feasible_buses,
            "buses_with_issues": buses_with_issues,
            "incidents_total": len(incidents),
            "incidents_error": error_issues,
            "incidents_warning": warning_issues,
            "incidents_info": info_issues,
        },
        "days": day_reports,
        "incidents": incidents,
    }


def _report_metrics_from_validation(
    report: Dict[str, Any],
    schedule_by_day_serialized: Dict[str, Any],
    optimizer_diagnostics_by_day: Optional[Dict[str, Dict[str, Any]]] = None,
    invalid_rows_dropped: int = 0,
) -> Dict[str, Any]:
    def _to_minutes(value: Any) -> Optional[int]:
        if value is None:
            return None
        if hasattr(value, "hour") and hasattr(value, "minute"):
            return (int(value.hour) * 60) + int(value.minute)
        if isinstance(value, str):
            try:
                hh, mm = [int(x) for x in value.split(":")[:2]]
                return (hh * 60) + mm
            except Exception:
                return None
        return None

    summary = report.get("summary", {})
    total_buses = sum(int(schedule_by_day_serialized.get(day, {}).get("stats", {}).get("total_buses", 0)) for day in ALL_DAYS)
    efficiencies: List[float] = []
    for day in ALL_DAYS:
        day_data = schedule_by_day_serialized.get(day, {})
        buses = day_data.get("schedule", [])
        day_eff = []
        for bus in buses:
            items = bus.get("items", [])
            if not items:
                continue
            total_minutes = 0
            work_minutes = 0
            try:
                start = items[0]["start_time"]
                end = items[-1]["end_time"]
                start_minutes = _to_minutes(start)
                end_minutes = _to_minutes(end)
                if start_minutes is not None and end_minutes is not None:
                    total_minutes = end_minutes - start_minutes
            except Exception:
                total_minutes = 0
            for item in items:
                try:
                    s = item["start_time"]
                    e = item["end_time"]
                    s_min = _to_minutes(s)
                    e_min = _to_minutes(e)
                    if s_min is not None and e_min is not None:
                        work_minutes += max(0, e_min - s_min)
                except Exception:
                    continue
            if total_minutes > 0:
                day_eff.append((work_minutes / total_minutes) * 100)
        if day_eff:
            efficiencies.extend(day_eff)

    avg_efficiency = sum(efficiencies) / len(efficiencies) if efficiencies else 0.0
    deadhead_values: List[int] = []
    routes_per_bus_all_days: List[int] = []
    per_day_spreads: List[int] = []
    per_day_abs_dev: List[float] = []
    for day in ALL_DAYS:
        day_data = schedule_by_day_serialized.get(day, {})
        day_counts: List[int] = []
        for bus in day_data.get("schedule", []):
            bus_count = int(len(bus.get("items", []) or []))
            if bus_count > 0:
                day_counts.append(bus_count)
                routes_per_bus_all_days.append(bus_count)
            for item in bus.get("items", []):
                value = item.get("deadhead_minutes")
                if isinstance(value, (int, float)):
                    deadhead_values.append(int(value))
        if day_counts:
            day_sorted = sorted(day_counts)
            day_med = float(median(day_sorted))
            per_day_spreads.append(int(day_sorted[-1] - day_sorted[0]))
            per_day_abs_dev.append(float(sum(abs(float(v) - day_med) for v in day_sorted)))
    avg_deadhead = (sum(deadhead_values) / len(deadhead_values)) if deadhead_values else 0.0
    avg_positioning = avg_deadhead

    if routes_per_bus_all_days:
        sorted_counts = sorted(routes_per_bus_all_days)
        median_routes = float(median(sorted_counts))
        min_routes = int(sorted_counts[0])
        max_routes = int(sorted_counts[-1])
    else:
        median_routes = 0.0
        min_routes = 0
        max_routes = 0
    load_spread_routes = int(max(per_day_spreads)) if per_day_spreads else 0
    load_abs_dev_sum = float(sum(per_day_abs_dev)) if per_day_abs_dev else 0.0

    infeasible_buses = max(0, int(summary.get("total_buses", 0)) - int(summary.get("feasible_buses", 0)))

    diagnostics = optimizer_diagnostics_by_day or {}
    split_count = 0
    lower_bound_buses = 0
    statuses: List[str] = []
    for day in ALL_DAYS:
        day_diag = diagnostics.get(day) or {}
        split_count += int(day_diag.get("split_count", 0) or 0)
        day_serialized = schedule_by_day_serialized.get(day, {})
        fallback_day_buses = int(day_serialized.get("stats", {}).get("total_buses", 0) or 0)
        lower_bound_buses += int(
            day_diag.get(
                "lower_bound_buses",
                fallback_day_buses,
            )
            or 0
        )
        status = str(day_diag.get("solver_status", "") or "").strip().lower()
        if status:
            statuses.append(status)

    best_buses = total_buses
    if lower_bound_buses <= 0:
        lower_bound_buses = best_buses
    optimality_gap = 0.0 if lower_bound_buses <= 0 else round(
        max(0, best_buses - lower_bound_buses) / float(lower_bound_buses),
        4,
    )

    solver_status = "feasible"
    if statuses and all(status == "optimal" for status in statuses):
        solver_status = "optimal"
    if any(status == "timeout" for status in statuses):
        solver_status = "timeout"
    if split_count > 0 and solver_status == "optimal":
        solver_status = "feasible"

    return {
        "infeasible_buses": infeasible_buses,
        "error_issues": int(summary.get("incidents_error", 0)),
        "warning_issues": int(summary.get("incidents_warning", 0)),
        "total_buses": total_buses,
        "best_buses": best_buses,
        "lower_bound_buses": lower_bound_buses,
        "optimality_gap": optimality_gap,
        "split_count": split_count,
        "solver_status": solver_status,
        "invalid_rows_dropped": int(invalid_rows_dropped),
        "avg_deadhead": round(avg_deadhead, 2),
        "avg_positioning_minutes": round(avg_positioning, 2),
        "avg_efficiency": round(avg_efficiency, 2),
        "median_routes_per_bus": round(median_routes, 2),
        "min_routes_per_bus": min_routes,
        "max_routes_per_bus": max_routes,
        "load_spread_routes": load_spread_routes,
        "load_abs_dev_sum": round(load_abs_dev_sum, 2),
        "load_balanced": bool(load_spread_routes <= 2),
    }


def _serialize_schedule_by_day(schedule_by_day: Dict[str, List[BusSchedule]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for day in ALL_DAYS:
        schedule = schedule_by_day.get(day, [])
        result[day] = {
            "schedule": [bus.dict() for bus in schedule],
            "stats": _calculate_stats(schedule),
            "day_name": DAY_NAMES[day],
        }
    return result


def _optimize_by_day_v6(
    routes: List[Route],
    use_ml_assignment: bool = True,
    balance_load: bool = True,
    load_balance_hard_spread_limit: int = 2,
    load_balance_target_band: int = 1,
    trace_callback: DayTraceCallback = None,
) -> Tuple[Dict[str, List[BusSchedule]], Dict[str, Dict[str, Any]]]:
    try:
        from optimizer_v6 import optimize_v6, get_last_optimization_diagnostics
    except ImportError:
        from backend.optimizer_v6 import optimize_v6, get_last_optimization_diagnostics

    by_day: Dict[str, List[BusSchedule]] = {}
    diagnostics_by_day: Dict[str, Dict[str, Any]] = {}
    for day in ALL_DAYS:
        day_routes = [route for route in routes if day in route.days]
        if trace_callback:
            trace_callback(
                day,
                "day_start",
                0,
                f"Iniciando optimizacion V6 para {len(day_routes)} rutas",
                {"engine": "v6"},
            )
        if day_routes:
            def _day_progress(phase: str, progress: int, message: str) -> None:
                if trace_callback:
                    trace_callback(
                        day,
                        phase,
                        progress,
                        message,
                        {"engine": "v6"},
                    )

            try:
                by_day[day] = optimize_v6(
                    day_routes,
                    progress_callback=_day_progress,
                    use_ml_assignment=use_ml_assignment,
                    balance_load=balance_load,
                    load_balance_hard_spread_limit=load_balance_hard_spread_limit,
                    load_balance_target_band=load_balance_target_band,
                )
                diagnostics_by_day[day] = get_last_optimization_diagnostics()
            except Exception as first_exc:
                logger.exception(
                    "[Pipeline] V6 failed for day %s (routes=%s). Retrying with conservative mode.",
                    day,
                    len(day_routes),
                )
                if trace_callback:
                    trace_callback(
                        day,
                        "day_retry",
                        55,
                        "Fallo en V6, reintentando en modo conservador",
                        {"engine": "v6", "error": f"{type(first_exc).__name__}: {first_exc}"},
                    )
                try:
                    by_day[day] = optimize_v6(
                        day_routes,
                        progress_callback=_day_progress,
                        use_ml_assignment=False,
                        balance_load=balance_load,
                        load_balance_hard_spread_limit=load_balance_hard_spread_limit,
                        load_balance_target_band=load_balance_target_band,
                    )
                    diagnostics_by_day[day] = dict(get_last_optimization_diagnostics() or {})
                    diagnostics_by_day[day]["solver_status"] = "fallback_ml_disabled"
                    diagnostics_by_day[day]["fallback_reason"] = f"{type(first_exc).__name__}: {first_exc}"
                except Exception as second_exc:
                    logger.exception(
                        "[Pipeline] V6 retry also failed for day %s. Using route-per-bus fallback.",
                        day,
                    )
                    by_day[day] = _build_route_per_bus_fallback(day_routes)
                    diagnostics_by_day[day] = {
                        "total_routes": len(day_routes),
                        "pre_split_buses": len(by_day[day]),
                        "best_buses": len(by_day[day]),
                        "split_count": 0,
                        "solver_status": "fallback_route_per_bus",
                        "lower_bound_buses": 0,
                        "optimality_gap": 0.0,
                        "fallback_reason": (
                            f"primary={type(first_exc).__name__}: {first_exc}; "
                            f"retry={type(second_exc).__name__}: {second_exc}"
                        ),
                    }
                    if trace_callback:
                        trace_callback(
                            day,
                            "day_fallback",
                            100,
                            "Fallback de seguridad aplicado (1 ruta por bus)",
                            {"engine": "v6", "fallback": "route_per_bus"},
                        )

            if trace_callback:
                day_stats = _calculate_stats(by_day[day])
                trace_callback(
                    day,
                    "day_completed",
                    100,
                    f"V6 completado: {day_stats.get('total_buses', 0)} buses",
                    {"engine": "v6", "day_stats": day_stats},
                )
        else:
            by_day[day] = []
            diagnostics_by_day[day] = {
                "total_routes": 0,
                "pre_split_buses": 0,
                "best_buses": 0,
                "split_count": 0,
                "solver_status": "optimal",
                "lower_bound_buses": 0,
                "optimality_gap": 0.0,
            }
            if trace_callback:
                trace_callback(
                    day,
                    "day_skipped",
                    100,
                    "Sin rutas para este dia",
                    {"engine": "v6"},
                )
    return by_day, diagnostics_by_day


def _optimize_by_day_lns(
    routes: List[Route],
    objective: str,
    use_ml_assignment: bool = True,
    balance_load: bool = True,
    load_balance_hard_spread_limit: int = 2,
    load_balance_target_band: int = 1,
    trace_callback: DayTraceCallback = None,
    iteration: int = 1,
) -> Tuple[Dict[str, List[BusSchedule]], Dict[str, Dict[str, Any]]]:
    try:
        from optimizer_lns import optimize_v6_lns
        from optimizer_multi import ObjectiveWeights, ObjectivePresets
        from optimizer_v6 import get_last_optimization_diagnostics
    except ImportError:
        from backend.optimizer_lns import optimize_v6_lns
        from backend.optimizer_multi import ObjectiveWeights, ObjectivePresets
        from backend.optimizer_v6 import get_last_optimization_diagnostics

    if objective in {"min_buses_viability", "min_buses_viability_hybrid"}:
        weights = ObjectivePresets.minimize_buses()
    else:
        weights = ObjectivePresets.balanced()

    by_day: Dict[str, List[BusSchedule]] = {}
    diagnostics_by_day: Dict[str, Dict[str, Any]] = {}
    for day in ALL_DAYS:
        day_routes = [route for route in routes if day in route.days]
        if trace_callback:
            trace_callback(
                day,
                "day_start",
                0,
                f"Iniciando reoptimizacion LNS iteracion {iteration} para {len(day_routes)} rutas",
                {"engine": "lns", "iteration": iteration},
            )
        if not day_routes:
            by_day[day] = []
            diagnostics_by_day[day] = {
                "total_routes": 0,
                "pre_split_buses": 0,
                "best_buses": 0,
                "split_count": 0,
                "solver_status": "optimal",
                "lower_bound_buses": 0,
                "optimality_gap": 0.0,
            }
            if trace_callback:
                trace_callback(
                    day,
                    "day_skipped",
                    100,
                    f"Iteracion {iteration}: sin rutas para este dia",
                    {"engine": "lns", "iteration": iteration},
                )
            continue

        def _day_progress(phase: str, progress: int, message: str) -> None:
            if trace_callback:
                trace_callback(
                    day,
                    phase,
                    progress,
                    message,
                    {"engine": "lns", "iteration": iteration},
                )

        by_day[day] = optimize_v6_lns(
            day_routes,
            weights=ObjectiveWeights(**weights.to_dict()),
            use_lns=True,
            progress_callback=_day_progress,
            use_ml_assignment=use_ml_assignment,
            balance_load=balance_load,
            load_balance_hard_spread_limit=load_balance_hard_spread_limit,
            load_balance_target_band=load_balance_target_band,
        )
        diagnostics_by_day[day] = get_last_optimization_diagnostics()
        if trace_callback:
            day_stats = _calculate_stats(by_day[day])
            trace_callback(
                day,
                "day_completed",
                100,
                f"LNS iteracion {iteration} completada: {day_stats.get('total_buses', 0)} buses",
                {"engine": "lns", "iteration": iteration, "day_stats": day_stats},
            )
    return by_day, diagnostics_by_day


async def _optimize_by_day_hybrid(
    routes: List[Route],
    seed_schedule_by_day: Dict[str, List[BusSchedule]],
    use_ml_assignment: bool = True,
    max_qubo_vars: int = 160,
) -> Tuple[Dict[str, List[BusSchedule]], Dict[str, Any]]:
    try:
        from services.hybrid_quantum_optimizer import optimize_by_day_hybrid
    except ImportError:
        from backend.services.hybrid_quantum_optimizer import optimize_by_day_hybrid

    return await optimize_by_day_hybrid(
        routes=routes,
        seed_schedule_by_day=seed_schedule_by_day,
        max_qubo_vars=max_qubo_vars,
        use_ml_assignment=use_ml_assignment,
    )


async def run_optimization_pipeline_by_day(
    routes: List[Route],
    config: PipelineConfig,
    progress_callback: Optional[Callable[..., None]] = None,
) -> Dict[str, Any]:
    """
    Ejecuta pipeline completo y retorna el mejor resultado validado.
    """
    started_at = now_seconds()
    history: List[Dict[str, Any]] = []
    event_loop = asyncio.get_running_loop()
    event_loop_thread_id = threading.get_ident()

    def _append_history(
        stage: str,
        progress: int,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "stage": stage,
            "progress": progress,
            "message": message,
        }
        if extra:
            entry.update(extra)
        history.append(entry)
        _safe_emit_progress(progress_callback, stage, progress, message, extra=extra)

    def add_history(stage: str, progress: int, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        if threading.get_ident() == event_loop_thread_id:
            _append_history(stage, progress, message, extra)
            return

        done = threading.Event()
        error_holder: Dict[str, Exception] = {}

        def _dispatch() -> None:
            try:
                _append_history(stage, progress, message, extra)
            except Exception as exc:
                error_holder["error"] = exc
            finally:
                done.set()

        event_loop.call_soon_threadsafe(_dispatch)
        done.wait()
        error = error_holder.get("error")
        if error:
            raise error

    def emit_day_trace(
        *,
        stage: str,
        progress_window: Tuple[int, int],
        day: str,
        phase: str,
        local_progress: int,
        message: str,
        iteration: Optional[int] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        window_start = int(progress_window[0])
        window_end = int(progress_window[1])
        if window_end < window_start:
            window_end = window_start
        bounded_local = max(0, min(100, int(local_progress)))
        mapped_progress = window_start + int(((window_end - window_start) * bounded_local) / 100.0)
        day_label = DAY_NAMES.get(day, day)
        trace_extra: Dict[str, Any] = {
            "stage": stage,
            "stream": "trace",
            "day": day,
            "day_label": day_label,
            "optimizer_phase": phase,
            "local_progress": bounded_local,
        }
        if iteration is not None:
            trace_extra["iteration"] = iteration
        if extra:
            trace_extra.update(extra)

        add_history(
            stage,
            mapped_progress,
            f"[{day_label}] {message}",
            trace_extra,
        )

    def build_result(candidate: Dict[str, Any]) -> Dict[str, Any]:
        elapsed_sec = round(now_seconds() - started_at, 2)
        assigned_schedule_by_day = candidate.get("schedule_by_day", {})
        fleet_assignment_summary: Dict[str, Any] = {
            "total_assigned": 0,
            "total_virtual_buses": 0,
            "days": {},
        }
        try:
            assigned_raw_by_day, fleet_assignment_summary = assign_fleet_profiles_to_schedule_by_day(
                candidate.get("schedule_by_day_raw", {}),
            )
            assigned_schedule_by_day = _serialize_schedule_by_day(assigned_raw_by_day)
        except Exception:
            assigned_schedule_by_day = candidate.get("schedule_by_day", {})

        summary_metrics = dict(candidate["metrics"] or {})
        summary_metrics["fleet_assigned"] = int(fleet_assignment_summary.get("total_assigned", 0))
        summary_metrics["fleet_virtual_buses"] = int(fleet_assignment_summary.get("total_virtual_buses", 0))
        add_history(
            "completed",
            100,
            "Pipeline completado",
            {"stage": "completed", "selected": candidate["label"], "elapsed_sec": elapsed_sec},
        )
        return {
            "schedule_by_day": assigned_schedule_by_day,
            "stats_by_day": {
                day: (
                    assigned_schedule_by_day.get(day, {}).get("stats")
                    or _calculate_stats([])
                )
                for day in ALL_DAYS
            },
            "validation_report": candidate["validation_report"],
            "pipeline_history": history,
            "objective_score": candidate["score"],
            "selected_candidate": candidate["label"],
            "config_applied": config.to_dict(),
            "summary_metrics": summary_metrics,
            "fleet_assignment": fleet_assignment_summary,
            "hybrid_metadata": candidate.get("hybrid_metadata", {}),
            "elapsed_sec": elapsed_sec,
        }

    def candidate_rank(metrics: Dict[str, Any]) -> Tuple[Any, ...]:
        return rank_pipeline_candidate(metrics)

    def is_acceptable(metrics: Dict[str, Any]) -> bool:
        return int(metrics.get("split_count", 0)) == 0

    add_history("ingest", 5, "Normalizando rutas por dia", {"stage": "ingest"})

    baseline_by_day, baseline_diagnostics = await asyncio.to_thread(
        _optimize_by_day_v6,
        routes,
        config.use_ml_assignment,
        config.balance_load,
        config.load_balance_hard_spread_limit,
        config.load_balance_target_band,
        lambda day, phase, progress, message, extra=None: emit_day_trace(
            stage="baseline_trace",
            progress_window=(10, 34),
            day=day,
            phase=phase,
            local_progress=progress,
            message=message,
            iteration=None,
            extra=extra,
        ),
    )
    add_history("baseline_optimize", 35, "Optimizacion base V6 completada", {"stage": "baseline_optimize"})

    baseline_report = await _validate_schedule_by_day(baseline_by_day)
    baseline_serialized = _serialize_schedule_by_day(baseline_by_day)
    baseline_metrics = _report_metrics_from_validation(
        baseline_report,
        baseline_serialized,
        optimizer_diagnostics_by_day=baseline_diagnostics,
        invalid_rows_dropped=config.invalid_rows_dropped,
    )
    baseline_score = calculate_pipeline_candidate_score(baseline_metrics)
    add_history(
        "osrm_validate",
        45,
        "Validacion OSRM base completada",
        {"stage": "osrm_validate", "metrics": baseline_metrics, "score": baseline_score},
    )

    best_candidate = {
        "label": "baseline",
        "schedule_by_day_raw": baseline_by_day,
        "schedule_by_day": baseline_serialized,
        "validation_report": baseline_report,
        "metrics": baseline_metrics,
        "score": baseline_score,
        "hybrid_metadata": {},
    }
    best_acceptable_candidate: Optional[Dict[str, Any]] = (
        best_candidate if is_acceptable(baseline_metrics) else None
    )
    if not best_acceptable_candidate:
        add_history(
            "baseline_rejected",
            47,
            "Baseline descartada para seleccion final por split_count > 0",
            {"stage": "baseline_rejected", "metrics": baseline_metrics, "score": baseline_score},
        )

    elapsed_after_baseline = now_seconds() - started_at
    if elapsed_after_baseline >= config.max_duration_sec:
        selected = best_acceptable_candidate or best_candidate
        add_history(
            "budget_reached",
            92,
            (
                "Tiempo maximo alcanzado tras validacion base "
                f"({config.max_duration_sec}s); se omiten iteraciones"
            ),
            {"stage": "budget_reached", "iteration": 0},
        )
        add_history(
            "select_best",
            97,
            "Seleccionando mejor solucion validada",
            {"stage": "select_best", "selected": selected["label"], "score": selected["score"]},
        )
        return build_result(selected)

    hybrid_mode = config.objective == "min_buses_viability_hybrid"

    for iteration in range(1, max(0, config.max_iterations) + 1):
        elapsed = now_seconds() - started_at
        if elapsed >= config.max_duration_sec:
            add_history(
                "budget_reached",
                92,
                f"Tiempo maximo alcanzado ({config.max_duration_sec}s), se detiene en iteracion {iteration}",
                {"stage": "budget_reached", "iteration": iteration},
            )
            break

        stage_name = f"reoptimize_iter_{iteration}"
        base_progress = 50 + (iteration * 15)
        add_history(
            stage_name,
            min(base_progress, 88),
            f"Reoptimizando (iteracion {iteration})",
            {
                "stage": stage_name,
                "iteration": iteration,
                "engine": "hybrid_qubo" if hybrid_mode else "lns",
            },
        )

        hybrid_meta: Dict[str, Any] = {}
        candidate_diagnostics: Dict[str, Dict[str, Any]] = {}
        try:
            if hybrid_mode:
                add_history(
                    f"qubo_encode_iter_{iteration}",
                    min(base_progress + 3, 90),
                    f"Codificando subproblemas QUBO (iteracion {iteration})",
                    {"stage": "qubo_encode", "iteration": iteration},
                )
                candidate_by_day, hybrid_meta = await _optimize_by_day_hybrid(
                    routes=routes,
                    seed_schedule_by_day=best_candidate.get("schedule_by_day_raw", {}),
                    use_ml_assignment=config.use_ml_assignment,
                    max_qubo_vars=160,
                )
                candidate_diagnostics = hybrid_meta.get("optimizer_diagnostics_by_day", {}) or {}
                add_history(
                    f"quantum_refine_iter_{iteration}",
                    min(base_progress + 6, 92),
                    f"Refinamiento quantum-inspired (iteracion {iteration}) completado",
                    {"stage": "quantum_refine", "iteration": iteration, "metrics": {"hybrid": hybrid_meta}},
                )
            else:
                candidate_by_day, candidate_diagnostics = await asyncio.to_thread(
                    _optimize_by_day_lns,
                    routes,
                    config.objective,
                    use_ml_assignment=config.use_ml_assignment,
                    balance_load=config.balance_load,
                    load_balance_hard_spread_limit=config.load_balance_hard_spread_limit,
                    load_balance_target_band=config.load_balance_target_band,
                    trace_callback=lambda day, phase, progress, message, extra=None: emit_day_trace(
                        stage=f"reoptimize_trace_{iteration}",
                        progress_window=(base_progress, min(base_progress + 7, 90)),
                        day=day,
                        phase=phase,
                        local_progress=progress,
                        message=message,
                        iteration=iteration,
                        extra=extra,
                    ),
                    iteration=iteration,
                )
        except Exception as iteration_exc:
            logger.exception("[Pipeline] Iteration %s failed during optimization", iteration)
            add_history(
                "iteration_failed",
                min(base_progress + 8, 94),
                f"Iteracion {iteration} fallida; se conserva la mejor solucion previa",
                {
                    "stage": "iteration_failed",
                    "iteration": iteration,
                    "error": f"{type(iteration_exc).__name__}: {iteration_exc}",
                },
            )
            break

        validation_stage = f"osrm_validate_iter_{iteration}"
        try:
            candidate_report = await _validate_schedule_by_day(candidate_by_day)
            candidate_serialized = _serialize_schedule_by_day(candidate_by_day)
            candidate_metrics = _report_metrics_from_validation(
                candidate_report,
                candidate_serialized,
                optimizer_diagnostics_by_day=candidate_diagnostics,
                invalid_rows_dropped=config.invalid_rows_dropped,
            )
            candidate_score = calculate_pipeline_candidate_score(candidate_metrics)
        except Exception as validation_exc:
            logger.exception("[Pipeline] Iteration %s failed during validation", iteration)
            add_history(
                "iteration_failed",
                min(base_progress + 8, 94),
                f"Iteracion {iteration} invalida por error de validacion",
                {
                    "stage": "iteration_failed",
                    "iteration": iteration,
                    "error": f"{type(validation_exc).__name__}: {validation_exc}",
                },
            )
            break

        progress_metrics = dict(candidate_metrics)
        if hybrid_meta:
            progress_metrics["hybrid"] = hybrid_meta

        add_history(
            validation_stage,
            min(base_progress + 8, 94),
            f"Validacion OSRM iteracion {iteration} completada",
            {
                "stage": validation_stage,
                "iteration": iteration,
                "metrics": progress_metrics,
                "score": candidate_score,
            },
        )

        candidate_payload = {
            "label": f"iteration_{iteration}",
            "schedule_by_day_raw": candidate_by_day,
            "schedule_by_day": candidate_serialized,
            "validation_report": candidate_report,
            "metrics": candidate_metrics,
            "score": candidate_score,
            "hybrid_metadata": hybrid_meta,
        }

        if candidate_score < best_candidate["score"]:
            best_candidate = candidate_payload

        if not is_acceptable(candidate_metrics):
            add_history(
                "candidate_rejected",
                min(base_progress + 9, 95),
                (
                    f"Iteracion {iteration} descartada en seleccion final: "
                    f"split_count={candidate_metrics.get('split_count', 0)}"
                ),
                {
                    "stage": "candidate_rejected",
                    "iteration": iteration,
                    "metrics": progress_metrics,
                    "score": candidate_score,
                },
            )
            continue

        if (
            best_acceptable_candidate is None
            or candidate_rank(candidate_metrics) < candidate_rank(best_acceptable_candidate["metrics"])
        ):
            best_acceptable_candidate = candidate_payload
            add_history(
                "improved",
                min(base_progress + 10, 95),
                f"Iteracion {iteration} mejora la solucion aceptable",
                {
                    "stage": "improved",
                    "iteration": iteration,
                    "metrics": progress_metrics,
                    "score": candidate_score,
                },
            )
        else:
            add_history(
                "no_improvement",
                min(base_progress + 10, 95),
                f"Iteracion {iteration} sin mejora aceptable; se detiene busqueda",
                {
                    "stage": "no_improvement",
                    "iteration": iteration,
                    "metrics": progress_metrics,
                    "score": candidate_score,
                },
            )
            break

        elapsed_after_iteration = now_seconds() - started_at
        if elapsed_after_iteration >= config.max_duration_sec:
            add_history(
                "budget_reached",
                94,
                (
                    "Tiempo maximo alcanzado tras iteracion "
                    f"{iteration} ({config.max_duration_sec}s)"
                ),
                {"stage": "budget_reached", "iteration": iteration},
            )
            break

    selected_candidate = best_acceptable_candidate or best_candidate
    if best_acceptable_candidate is None:
        add_history(
            "select_with_risk",
            96,
            "No hubo candidato con split_count=0; se selecciona mejor candidato disponible",
            {"stage": "select_with_risk", "selected": selected_candidate["label"]},
        )

    add_history(
        "select_best",
        97,
        "Seleccionando mejor solucion validada",
        {"stage": "select_best", "selected": selected_candidate["label"], "score": selected_candidate["score"]},
    )

    return build_result(selected_candidate)
