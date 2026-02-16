"""
Hybrid (quantum-inspired) optimizer for route assignment refinement.

Phase 1 strategy:
1) Start from V6/LNS seed schedule.
2) Detect high-conflict routes with OSRM validation.
3) Encode a reduced reassignment problem as QUBO.
4) Solve with simulated annealing (quantum-inspired).
5) Apply reassignment and return refined schedule.
"""

from __future__ import annotations

import bisect
from collections import Counter
from dataclasses import dataclass
from datetime import time
from typing import Any, Dict, List, Optional, Tuple

try:
    from models import BusSchedule, Route, ScheduleItem
except ImportError:
    from backend.models import BusSchedule, Route, ScheduleItem

DAY_CODES = ["L", "M", "Mc", "X", "V"]


@dataclass
class DayHybridMetadata:
    day: str
    selected_routes: int
    qubo_variables: int
    qubo_energy: float
    moved_routes: int
    hot_routes: int
    initial_errors: int
    final_errors: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "day": self.day,
            "selected_routes": self.selected_routes,
            "qubo_variables": self.qubo_variables,
            "qubo_energy": round(self.qubo_energy, 3),
            "moved_routes": self.moved_routes,
            "hot_routes": self.hot_routes,
            "initial_errors": self.initial_errors,
            "final_errors": self.final_errors,
        }


def _clone_schedule(schedule: List[BusSchedule]) -> List[BusSchedule]:
    cloned: List[BusSchedule] = []
    for bus in schedule:
        if hasattr(bus, "model_copy"):
            cloned.append(bus.model_copy(deep=True))
        else:
            cloned.append(bus.copy(deep=True))
    return cloned


def _time_to_minutes(value: time) -> int:
    return int(value.hour) * 60 + int(value.minute)


def _bus_sort_key(bus_id: str) -> Tuple[int, str]:
    digits = "".join(ch for ch in (bus_id or "") if ch.isdigit())
    number = int(digits) if digits else 999999
    return (number, bus_id or "")


def _next_bus_id(schedule: List[BusSchedule]) -> str:
    max_num = 0
    for bus in schedule:
        digits = "".join(ch for ch in (bus.bus_id or "") if ch.isdigit())
        if digits:
            max_num = max(max_num, int(digits))
    return f"B{max_num + 1:03d}"


def _route_map(schedule: List[BusSchedule]) -> Dict[str, Tuple[str, ScheduleItem]]:
    mapping: Dict[str, Tuple[str, ScheduleItem]] = {}
    for bus in schedule:
        for item in bus.items:
            mapping[item.route_id] = (bus.bus_id, item)
    return mapping


def _get_item_locations(item: ScheduleItem) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    stops = item.stops or []
    if stops:
        first = stops[0]
        last = stops[-1]
        return (float(first.lat), float(first.lon)), (float(last.lat), float(last.lon))
    return (0.0, 0.0), (0.0, 0.0)


def _to_assigned_route(item: ScheduleItem):
    try:
        from models.validation_result import AssignedRoute
    except ImportError:
        from backend.models.validation_result import AssignedRoute

    start_loc, end_loc = _get_item_locations(item)
    return AssignedRoute(
        id=item.route_id,
        route_id=item.route_id,
        start_time=item.start_time,
        end_time=item.end_time,
        start_location=start_loc,
        end_location=end_loc,
        type=item.type,
        school_name=item.school_name,
    )


async def _collect_bus_issues(schedule: List[BusSchedule], validator: Any) -> Tuple[List[Dict[str, Any]], int]:
    issues: List[Dict[str, Any]] = []
    error_count = 0

    for bus in schedule:
        assigned = [_to_assigned_route(item) for item in sorted(bus.items, key=lambda x: _time_to_minutes(x.start_time))]
        result = await validator.validate_bus_schedule(assigned)
        for issue in result.issues:
            issue_data = issue.dict()
            issue_data["bus_id"] = bus.bus_id
            issues.append(issue_data)
            if issue_data.get("severity", "error") == "error":
                error_count += 1
    return issues, error_count


async def _connection_penalty(validator: Any, left: Optional[ScheduleItem], right: Optional[ScheduleItem]) -> float:
    if left is None or right is None:
        return 0.0

    result = await validator.validate_connection(_to_assigned_route(left), _to_assigned_route(right))
    buffer = float(result.buffer_minutes)
    time_available = float(result.time_available)

    if time_available < 0:
        return 2200.0 + abs(time_available) * 80.0
    if buffer < 0:
        return 900.0 + abs(buffer) * 45.0
    if buffer < 5:
        return 120.0 + (5.0 - buffer) * 20.0
    if buffer > 35:
        return (buffer - 35.0) * 0.8
    return 0.0


async def _evaluate_insertion_cost(
    validator: Any,
    bus: BusSchedule,
    route_item: ScheduleItem,
    insertion_index: int,
    source_bus_id: str,
) -> float:
    items = sorted(bus.items, key=lambda x: _time_to_minutes(x.start_time))
    idx = max(0, min(insertion_index, len(items)))
    prev_item = items[idx - 1] if idx > 0 else None
    next_item = items[idx] if idx < len(items) else None

    penalty = 0.0
    penalty += await _connection_penalty(validator, prev_item, route_item)
    penalty += await _connection_penalty(validator, route_item, next_item)
    penalty += len(items) * 1.5

    if bus.bus_id != source_bus_id:
        penalty += 8.0
    return penalty


def _candidate_positions(bus: BusSchedule, route_item: ScheduleItem) -> List[int]:
    ordered = sorted(bus.items, key=lambda x: _time_to_minutes(x.start_time))
    starts = [_time_to_minutes(item.start_time) for item in ordered]
    target_start = _time_to_minutes(route_item.start_time)
    pivot = bisect.bisect_left(starts, target_start)
    options = {
        max(0, pivot - 1),
        max(0, pivot),
        min(len(ordered), pivot + 1),
        len(ordered),
    }
    return sorted(options)


async def _build_route_candidates(
    schedule: List[BusSchedule],
    selected_route_ids: List[str],
    validator: Any,
    max_buses_per_route: int = 5,
) -> Dict[str, List[Dict[str, Any]]]:
    route_lookup = _route_map(schedule)
    buses_sorted = sorted(schedule, key=lambda b: _bus_sort_key(b.bus_id))
    route_candidates: Dict[str, List[Dict[str, Any]]] = {}

    for route_id in selected_route_ids:
        if route_id not in route_lookup:
            continue

        source_bus_id, route_item = route_lookup[route_id]
        source_bus = next((b for b in buses_sorted if b.bus_id == source_bus_id), None)
        if source_bus is None:
            continue

        route_start = _time_to_minutes(route_item.start_time)
        route_end = _time_to_minutes(route_item.end_time)

        # prioritize buses close in time to reduce candidate explosion
        def temporal_distance(bus: BusSchedule) -> int:
            if not bus.items:
                return 0
            bus_starts = [_time_to_minutes(i.start_time) for i in bus.items]
            return min(abs(route_start - s) for s in bus_starts)

        candidate_buses = sorted(buses_sorted, key=temporal_distance)[:max_buses_per_route]
        if source_bus not in candidate_buses:
            candidate_buses.append(source_bus)

        candidates: List[Dict[str, Any]] = []
        for bus in candidate_buses:
            for insertion_index in _candidate_positions(bus, route_item):
                cost = await _evaluate_insertion_cost(
                    validator=validator,
                    bus=bus,
                    route_item=route_item,
                    insertion_index=insertion_index,
                    source_bus_id=source_bus_id,
                )
                candidates.append(
                    {
                        "route_id": route_id,
                        "source_bus_id": source_bus_id,
                        "target_bus_id": bus.bus_id,
                        "insertion_index": insertion_index,
                        "cost": cost,
                        "window_start_min": route_start,
                        "window_end_min": route_end,
                    }
                )

        # synthetic "new bus" candidate, expensive but available
        candidates.append(
            {
                "route_id": route_id,
                "source_bus_id": source_bus_id,
                "target_bus_id": "__NEW__",
                "insertion_index": 0,
                "cost": 140.0,
                "window_start_min": route_start,
                "window_end_min": route_end,
            }
        )

        # keep best candidates only
        route_candidates[route_id] = sorted(candidates, key=lambda c: float(c["cost"]))[:8]

    return route_candidates


def _apply_selected_assignments(
    schedule: List[BusSchedule],
    selected_variables: List[Any],
) -> Tuple[List[BusSchedule], int]:
    working = _clone_schedule(schedule)
    route_lookup = _route_map(working)
    selected_route_ids = {var.route_id for var in selected_variables}

    # Remove selected routes from all buses.
    for bus in working:
        bus.items = [item for item in bus.items if item.route_id not in selected_route_ids]

    bus_by_id: Dict[str, BusSchedule] = {bus.bus_id: bus for bus in working}
    new_bus_items: List[ScheduleItem] = []
    moved_routes = 0

    for variable in selected_variables:
        route_data = route_lookup.get(variable.route_id)
        if not route_data:
            continue
        source_bus_id, source_item = route_data
        route_item = source_item.model_copy(deep=True) if hasattr(source_item, "model_copy") else source_item.copy(deep=True)
        target_bus_id = variable.target_bus_id

        if target_bus_id == "__NEW__":
            new_bus_items.append(route_item)
            if source_bus_id != "__NEW__":
                moved_routes += 1
            continue

        target_bus = bus_by_id.get(target_bus_id)
        if target_bus is None:
            target_bus = BusSchedule(bus_id=target_bus_id, items=[])
            working.append(target_bus)
            bus_by_id[target_bus_id] = target_bus

        insert_at = max(0, min(variable.insertion_index, len(target_bus.items)))
        target_bus.items.insert(insert_at, route_item)
        if source_bus_id != target_bus_id:
            moved_routes += 1

    if new_bus_items:
        new_id = _next_bus_id(working)
        new_bus_items = sorted(new_bus_items, key=lambda x: _time_to_minutes(x.start_time))
        working.append(BusSchedule(bus_id=new_id, items=new_bus_items))
        moved_routes += len(new_bus_items)

    # Cleanup and sort schedule
    cleaned: List[BusSchedule] = []
    for bus in working:
        ordered = sorted(bus.items, key=lambda x: _time_to_minutes(x.start_time))
        if ordered:
            bus.items = ordered
            cleaned.append(bus)
    cleaned.sort(key=lambda b: _bus_sort_key(b.bus_id))

    return cleaned, moved_routes


async def optimize_day_hybrid(
    *,
    day: str,
    day_routes: List[Route],
    seed_schedule: Optional[List[BusSchedule]],
    max_qubo_vars: int = 160,
    use_ml_assignment: bool = True,
) -> Tuple[List[BusSchedule], Dict[str, Any]]:
    """
    Refine a day schedule with QUBO-based reassignment for conflict-heavy routes.
    """
    if not day_routes:
        return [], DayHybridMetadata(
            day=day,
            selected_routes=0,
            qubo_variables=0,
            qubo_energy=0.0,
            moved_routes=0,
            hot_routes=0,
            initial_errors=0,
            final_errors=0,
        ).to_dict()

    try:
        from services.manual_schedule_validator import ManualScheduleValidator, OSRMService
    except ImportError:
        from backend.services.manual_schedule_validator import ManualScheduleValidator, OSRMService

    try:
        from services.qubo_encoder import build_assignment_qubo
    except ImportError:
        from backend.services.qubo_encoder import build_assignment_qubo

    try:
        from services.quantum_backends import solve_qubo_simulated_annealing
    except ImportError:
        from backend.services.quantum_backends import solve_qubo_simulated_annealing

    if seed_schedule is None:
        try:
            from optimizer_v6 import optimize_v6
        except ImportError:
            from backend.optimizer_v6 import optimize_v6
        base_schedule = optimize_v6(day_routes, use_ml_assignment=use_ml_assignment)
    else:
        base_schedule = _clone_schedule(seed_schedule)

    validator = ManualScheduleValidator(OSRMService())
    issues, initial_errors = await _collect_bus_issues(base_schedule, validator)
    if initial_errors <= 0:
        return base_schedule, DayHybridMetadata(
            day=day,
            selected_routes=0,
            qubo_variables=0,
            qubo_energy=0.0,
            moved_routes=0,
            hot_routes=0,
            initial_errors=0,
            final_errors=0,
        ).to_dict()

    route_counter: Counter = Counter()
    for issue in issues:
        if issue.get("severity") != "error":
            continue
        if issue.get("route_b"):
            route_counter[str(issue["route_b"])] += 2
        if issue.get("route_a"):
            route_counter[str(issue["route_a"])] += 1

    hot_route_ids = [route_id for route_id, _ in route_counter.most_common(18)]
    route_candidates = await _build_route_candidates(base_schedule, hot_route_ids, validator)
    if not route_candidates:
        return base_schedule, DayHybridMetadata(
            day=day,
            selected_routes=0,
            qubo_variables=0,
            qubo_energy=0.0,
            moved_routes=0,
            hot_routes=len(hot_route_ids),
            initial_errors=initial_errors,
            final_errors=initial_errors,
        ).to_dict()

    qubo_problem = build_assignment_qubo(route_candidates=route_candidates)
    if int(qubo_problem.metadata.get("num_variables", 0)) > max_qubo_vars:
        # Keep only top routes until max variable limit.
        trimmed_routes: Dict[str, List[Dict[str, Any]]] = {}
        variable_budget = max_qubo_vars
        for route_id in hot_route_ids:
            options = route_candidates.get(route_id, [])
            if not options:
                continue
            if variable_budget - len(options) < 0:
                continue
            trimmed_routes[route_id] = options
            variable_budget -= len(options)
            if variable_budget <= 0:
                break
        qubo_problem = build_assignment_qubo(route_candidates=trimmed_routes)

    solution = solve_qubo_simulated_annealing(
        qubo_problem,
        max_iterations=3000,
    )
    selected_vars = [
        qubo_problem.variables[idx]
        for idx in solution.active_indexes
        if 0 <= idx < len(qubo_problem.variables)
    ]
    refined_schedule, moved_routes = _apply_selected_assignments(base_schedule, selected_vars)
    _, final_errors = await _collect_bus_issues(refined_schedule, validator)

    metadata = DayHybridMetadata(
        day=day,
        selected_routes=len(selected_vars),
        qubo_variables=int(qubo_problem.metadata.get("num_variables", 0)),
        qubo_energy=float(solution.energy),
        moved_routes=moved_routes,
        hot_routes=len(hot_route_ids),
        initial_errors=initial_errors,
        final_errors=final_errors,
    ).to_dict()
    return refined_schedule, metadata


async def optimize_by_day_hybrid(
    *,
    routes: List[Route],
    seed_schedule_by_day: Optional[Dict[str, List[BusSchedule]]] = None,
    max_qubo_vars: int = 160,
    use_ml_assignment: bool = True,
) -> Tuple[Dict[str, List[BusSchedule]], Dict[str, Any]]:
    """
    Run hybrid refinement independently for each weekday.
    """
    schedule_by_day: Dict[str, List[BusSchedule]] = {}
    meta_by_day: Dict[str, Any] = {}

    for day in DAY_CODES:
        day_routes = [route for route in routes if day in route.days]
        seed_schedule = (seed_schedule_by_day or {}).get(day)
        refined_schedule, metadata = await optimize_day_hybrid(
            day=day,
            day_routes=day_routes,
            seed_schedule=seed_schedule,
            max_qubo_vars=max_qubo_vars,
            use_ml_assignment=use_ml_assignment,
        )
        schedule_by_day[day] = refined_schedule
        meta_by_day[day] = metadata

    return schedule_by_day, meta_by_day
