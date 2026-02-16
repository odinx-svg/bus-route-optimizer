"""
Fleet assignment helpers for optimized schedules.

This module assigns optimized bus timelines to real fleet vehicles by seat
compatibility, while keeping optimizer chaining untouched.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

try:
    from models import BusSchedule, ScheduleItem
except ImportError:
    from backend.models import BusSchedule, ScheduleItem

try:
    from services.fleet_registry import FleetRegistry
except ImportError:
    from backend.services.fleet_registry import FleetRegistry

SMALL_SERVICE_MAX_SEATS = 9
SMALL_BUS_MAX_SEATS = 25


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return parsed


def _clone_bus(bus: BusSchedule) -> BusSchedule:
    if hasattr(bus, "model_copy"):
        return bus.model_copy(deep=True)  # Pydantic v2
    return bus.copy(deep=True)  # Pydantic v1 fallback


def _item_required_seats(item: ScheduleItem) -> int:
    direct = _safe_int(getattr(item, "capacity_needed", 0), 0)
    if direct > 0:
        return direct

    peak_stop = 0
    for stop in getattr(item, "stops", []) or []:
        peak_stop = max(peak_stop, _safe_int(getattr(stop, "passengers", 0), 0))
    if peak_stop > 0:
        return peak_stop

    cap_max = _safe_int(getattr(item, "vehicle_capacity_max", 0), 0)
    if cap_max > 0:
        return cap_max

    cap_min = _safe_int(getattr(item, "vehicle_capacity_min", 0), 0)
    if cap_min > 0:
        return cap_min

    return 1


def _bus_required_seats(bus: BusSchedule) -> int:
    if not bus.items:
        return 1
    return max(_item_required_seats(item) for item in bus.items)


def _normalize_vehicle(vehicle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    seats_max = _safe_int(vehicle.get("seats_max"), 0)
    if seats_max <= 0:
        return None
    seats_min = _safe_int(vehicle.get("seats_min"), 1)
    seats_min = max(1, min(seats_min, seats_max))
    return {
        "id": str(vehicle.get("id", "") or ""),
        "vehicle_code": str(vehicle.get("vehicle_code", "") or "").strip(),
        "plate": str(vehicle.get("plate", "") or "").strip(),
        "status": str(vehicle.get("status", "active") or "active").strip().lower(),
        "seats_min": seats_min,
        "seats_max": seats_max,
    }


def _fleet_score_for_requirement(vehicle: Dict[str, Any], required: int) -> Tuple[int, int, int]:
    seats_min = int(vehicle["seats_min"])
    seats_max = int(vehicle["seats_max"])
    overflow = max(0, seats_max - required)
    under_min_penalty = max(0, seats_min - required) * 15

    small_service_penalty = 0
    if required <= SMALL_SERVICE_MAX_SEATS and seats_max > SMALL_BUS_MAX_SEATS:
        # Stricter with very small services: avoid assigning medium/large buses.
        small_service_penalty = 120 + max(0, seats_max - SMALL_BUS_MAX_SEATS)

    return (small_service_penalty + under_min_penalty + overflow, seats_max, seats_min)


def load_active_fleet_profiles() -> List[Dict[str, Any]]:
    registry = FleetRegistry()
    profiles: List[Dict[str, Any]] = []
    for raw in registry.list_vehicles():
        normalized = _normalize_vehicle(raw)
        if not normalized:
            continue
        if normalized["status"] != "active":
            continue
        profiles.append(normalized)
    profiles.sort(key=lambda x: (int(x["seats_max"]), int(x["seats_min"]), str(x["vehicle_code"])))
    return profiles


def assign_fleet_profiles_to_schedule(
    schedule: List[BusSchedule],
    fleet_profiles: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[List[BusSchedule], Dict[str, Any]]:
    """
    Assign each optimized bus timeline to one real vehicle profile by capacity.

    Returns:
        (assigned_schedule, assignment_summary)
    """
    cloned_schedule = [_clone_bus(bus) for bus in (schedule or [])]
    if not cloned_schedule:
        return [], {
            "fleet_available": 0,
            "fleet_assigned": 0,
            "virtual_buses": 0,
            "unmatched_bus_ids": [],
        }

    fleet = list(fleet_profiles) if fleet_profiles is not None else load_active_fleet_profiles()
    normalized_fleet: List[Dict[str, Any]] = []
    for raw in fleet:
        normalized = _normalize_vehicle(raw)
        if normalized:
            normalized_fleet.append(normalized)
    normalized_fleet.sort(key=lambda x: (int(x["seats_max"]), int(x["seats_min"]), str(x["vehicle_code"])))

    required_by_index: Dict[int, int] = {
        idx: _bus_required_seats(bus)
        for idx, bus in enumerate(cloned_schedule)
    }
    assign_order = sorted(
        required_by_index.keys(),
        key=lambda idx: (-required_by_index[idx], str(cloned_schedule[idx].bus_id)),
    )

    available = list(normalized_fleet)
    assigned_count = 0
    unmatched: List[str] = []

    for idx in assign_order:
        bus = cloned_schedule[idx]
        required = required_by_index[idx]
        bus.min_required_seats = int(required)

        compatible = [
            vehicle for vehicle in available
            if int(vehicle["seats_max"]) >= required
        ]
        if compatible:
            compatible.sort(key=lambda vehicle: _fleet_score_for_requirement(vehicle, required))
            chosen = compatible[0]
            available = [vehicle for vehicle in available if vehicle["id"] != chosen["id"]]

            bus.uses_fleet_profile = True
            bus.assigned_vehicle_id = str(chosen["id"] or "")
            bus.assigned_vehicle_code = str(chosen["vehicle_code"] or "") or None
            bus.assigned_vehicle_plate = str(chosen["plate"] or "") or None
            bus.assigned_vehicle_seats_min = int(chosen["seats_min"])
            bus.assigned_vehicle_seats_max = int(chosen["seats_max"])
            assigned_count += 1
        else:
            bus.uses_fleet_profile = False
            bus.assigned_vehicle_id = None
            bus.assigned_vehicle_code = None
            bus.assigned_vehicle_plate = None
            bus.assigned_vehicle_seats_min = None
            bus.assigned_vehicle_seats_max = None
            unmatched.append(str(bus.bus_id))

    summary = {
        "fleet_available": len(normalized_fleet),
        "fleet_assigned": assigned_count,
        "virtual_buses": max(0, len(cloned_schedule) - assigned_count),
        "unmatched_bus_ids": unmatched,
    }
    return cloned_schedule, summary


def assign_fleet_profiles_to_schedule_by_day(
    schedule_by_day: Dict[str, List[BusSchedule]],
    fleet_profiles: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Dict[str, List[BusSchedule]], Dict[str, Any]]:
    fleet = list(fleet_profiles) if fleet_profiles is not None else load_active_fleet_profiles()
    assigned_by_day: Dict[str, List[BusSchedule]] = {}
    summary_by_day: Dict[str, Any] = {}
    total_assigned = 0
    total_virtual = 0
    for day, day_schedule in (schedule_by_day or {}).items():
        assigned_schedule, summary = assign_fleet_profiles_to_schedule(day_schedule, fleet_profiles=fleet)
        assigned_by_day[day] = assigned_schedule
        summary_by_day[day] = summary
        total_assigned += int(summary.get("fleet_assigned", 0))
        total_virtual += int(summary.get("virtual_buses", 0))
    aggregate = {
        "total_assigned": total_assigned,
        "total_virtual_buses": total_virtual,
        "days": summary_by_day,
    }
    return assigned_by_day, aggregate
