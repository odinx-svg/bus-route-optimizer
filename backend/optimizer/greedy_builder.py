"""Deterministic greedy builder used as warm-start candidate and fallback baseline."""

from __future__ import annotations

import math
from datetime import time
from typing import Any, Dict, List, Optional, Tuple

from models import BusSchedule, Route, ScheduleItem

MIN_CONNECTION_BUFFER_MINUTES = 5
FALLBACK_SPEED_KMH = 35.0


def _to_minutes(value: Optional[time]) -> Optional[int]:
    if not isinstance(value, time):
        return None
    return (value.hour * 60) + value.minute


def _minutes_to_time(total_minutes: int) -> time:
    normalized = int(total_minutes) % (24 * 60)
    return time(hour=normalized // 60, minute=normalized % 60)


def _route_duration_minutes(route: Route) -> int:
    if not route.stops:
        return 0
    return max(int(stop.time_from_start or 0) for stop in route.stops)


def _route_window(route: Route) -> Tuple[int, int]:
    duration = _route_duration_minutes(route)
    if str(route.type or "").lower() == "entry":
        end_min = _to_minutes(route.arrival_time) or duration
        start_min = max(0, end_min - duration)
        return start_min, end_min
    start_min = _to_minutes(route.departure_time) or 0
    end_min = start_min + duration
    return start_min, end_min


def _route_endpoints(route: Route) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    if not route.stops:
        return (0.0, 0.0), (0.0, 0.0)
    first = route.stops[0]
    last = route.stops[-1]
    return (float(first.lat), float(first.lon)), (float(last.lat), float(last.lon))


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    if not any([lat1, lon1, lat2, lon2]):
        return 0.0
    radius = 6371.0
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _estimate_positioning_minutes(previous_route: Route, next_route: Route) -> int:
    (_, _), (prev_lat, prev_lon) = _route_endpoints(previous_route)
    (next_lat, next_lon), _ = _route_endpoints(next_route)
    distance_km = _haversine_km(prev_lat, prev_lon, next_lat, next_lon)
    travel_hours = distance_km / FALLBACK_SPEED_KMH if FALLBACK_SPEED_KMH > 0 else 0.0
    return int(round(travel_hours * 60))


def _build_schedule_item(route: Route, positioning_minutes: int = 0) -> ScheduleItem:
    start_min, end_min = _route_window(route)
    original_start = route.arrival_time if str(route.type or "").lower() == "entry" else route.departure_time
    return ScheduleItem(
        route_id=route.id,
        start_time=_minutes_to_time(start_min),
        end_time=_minutes_to_time(end_min),
        original_start_time=original_start,
        type=route.type,
        time_shift_minutes=0,
        deadhead_minutes=max(0, int(positioning_minutes)),
        positioning_minutes=max(0, int(positioning_minutes)),
        capacity_needed=int(route.capacity_needed or 0),
        vehicle_capacity_min=route.vehicle_capacity_min,
        vehicle_capacity_max=route.vehicle_capacity_max,
        vehicle_capacity_range=route.vehicle_capacity_range,
        school_name=route.school_name,
        stops=list(route.stops or []),
        contract_id=route.contract_id,
    )


def build_greedy_schedule(routes: List[Route]) -> List[BusSchedule]:
    """Build a deterministic feasible schedule by earliest start and smallest idle gap."""
    if not routes:
        return []

    buses: List[Dict[str, Any]] = []
    indexed_routes = sorted(
        routes,
        key=lambda route: (
            _route_window(route)[0],
            _route_window(route)[1],
            -int(route.capacity_needed or 0),
            str(route.id),
        ),
    )

    for route in indexed_routes:
        route_start, _ = _route_window(route)
        best_idx: Optional[int] = None
        best_rank: Optional[Tuple[int, int, int]] = None

        for idx, bus in enumerate(buses):
            previous_route: Route = bus["last_route"]
            previous_end = bus["last_end_minute"]
            positioning = _estimate_positioning_minutes(previous_route, route)
            earliest_start = previous_end + positioning + MIN_CONNECTION_BUFFER_MINUTES
            if earliest_start > route_start:
                continue

            idle_gap = max(0, route_start - earliest_start)
            required_seats = max(int(bus["min_required_seats"]), int(route.capacity_needed or 0))
            rank = (idle_gap, positioning, required_seats)
            if best_rank is None or rank < best_rank:
                best_rank = rank
                best_idx = idx

        if best_idx is None:
            buses.append({
                "items": [_build_schedule_item(route, positioning_minutes=0)],
                "last_route": route,
                "last_end_minute": _route_window(route)[1],
                "min_required_seats": int(route.capacity_needed or 0),
            })
            continue

        bus = buses[best_idx]
        positioning = _estimate_positioning_minutes(bus["last_route"], route)
        bus["items"].append(_build_schedule_item(route, positioning_minutes=positioning))
        bus["last_route"] = route
        bus["last_end_minute"] = _route_window(route)[1]
        bus["min_required_seats"] = max(int(bus["min_required_seats"]), int(route.capacity_needed or 0))

    return [
        BusSchedule(
            bus_id=f"B{index:03d}",
            items=bus["items"],
            min_required_seats=int(bus["min_required_seats"]),
        )
        for index, bus in enumerate(buses, start=1)
    ]
