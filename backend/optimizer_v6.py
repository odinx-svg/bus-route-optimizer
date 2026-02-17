"""
Optimizer V6 - Tutti Route Optimizer (ILP + Local Search)
=========================================================

GOAL: Minimize buses by optimal chaining using Integer Linear Programming.

IMPROVEMENTS OVER V5:
- ILP-based intra-block chain building (provably optimal minimum path cover)
- ILP-based cross-block matching (maximum bipartite matching)
- Local search improvement phase (relocate, swap)
- Unified travel time matrix (all OSRM calls upfront)
- Coordinate validation and exit stop order correction
- Transparent scoring and diagnostics

REAL SCHEDULE HAS 4 TIME BLOCKS:
1. Morning entries (08:00-09:30): Pickup kids -> deliver to school. LIMITED shift (+/-5).
2. Early afternoon exits (14:00-16:10): School ends -> deliver kids home. LIMITED shift (-5/+10).
3. Late afternoon entries (16:20-16:40): Pickup kids -> deliver to school. LIMITED shift (+/-5).
4. Late afternoon exits (18:20-18:40): School ends -> deliver kids home. LIMITED shift (-5/+10).

Uses OSRM for real driving times via router_service.py.
Uses PuLP (CBC solver) for ILP optimization.
"""

import logging
import math
import time as time_module
import os
import sys
from typing import List, Dict, Tuple, Optional, Set, Any
from datetime import time
from dataclasses import dataclass, field
from copy import deepcopy

import pulp

from models import Route, BusSchedule, ScheduleItem, Stop
from router_service import (
    get_real_travel_time,
    get_route_duration,
    get_router_metrics,
    get_travel_time_matrix,
    reset_router_metrics,
    save_cache,
)

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

MAX_ENTRY_SHIFT_MINUTES: int = 5      # Entradas: +/- 5 min
MAX_EXIT_EARLY_SHIFT_MINUTES: int = 5  # Salidas: hasta 5 min antes
MAX_EXIT_LATE_SHIFT_MINUTES: int = 10  # Salidas: hasta 10 min despues
MIN_CONNECTION_BUFFER_MINUTES: int = 5
DEADHEAD_BUFFER_MINUTES: int = 3
FALLBACK_SPEED_KMH: int = 50
EARTH_RADIUS_KM: float = 6371.0

SMALL_SERVICE_MAX_SEATS: int = 9
SMALL_BUS_MAX_SEATS: int = 25
SMALL_BUS_CAPACITY_MAX_DIFF: int = 8
CAPACITY_MAX_DIFF: int = 20
LARGE_ROUTE_MIN_SEATS: int = 56
LARGE_TO_SMALL_BLOCK_SEATS: int = 35
CROSS_BLOCK_FLEX_MINUTES: int = 0
CROSS_BLOCK_SCHOOL_BONUS: float = 12.0
CROSS_BLOCK_CAPACITY_BONUS: float = 4.0
CROSS_BLOCK_SMALL_SERVICE_BONUS: float = 12.0
CROSS_BLOCK_CAPACITY_PENALTY: float = 8.0

MORNING_ENTRY_MAX: int = 11 * 60
EARLY_EXIT_MAX: int = 16 * 60 + 15
LATE_ENTRY_MAX: int = 18 * 60

ILP_TIME_LIMIT: int = 15        # seconds per ILP solve (exits/block4 only)
LOCAL_SEARCH_TIME_LIMIT: int = 30  # seconds for local search phase
ILP_ENTRY_TIME_LIMIT: int = 60  # more time for entries with time constraints
MIN_START_HOUR: int = 6          # earliest bus can start (6:00 AM)


def _resolve_cbc_executable() -> Optional[str]:
    """Resolve CBC executable path for source and frozen desktop runtimes."""
    env_path = os.getenv("PULP_CBC_PATH", "").strip()
    candidates: List[str] = []
    if env_path:
        candidates.append(env_path)

    base_dir = os.path.dirname(__file__)
    candidates.extend(
        [
            os.path.join(base_dir, "bin", "cbc.exe"),
            os.path.join(base_dir, "solverdir", "cbc", "win", "i64", "cbc.exe"),
            os.path.join(base_dir, "..", "backend", "bin", "cbc.exe"),
        ]
    )

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.extend(
            [
                os.path.join(meipass, "backend", "bin", "cbc.exe"),
                os.path.join(meipass, "pulp", "solverdir", "cbc", "win", "i64", "cbc.exe"),
            ]
        )

    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def _build_cbc_solver(time_limit_seconds: int):
    """Build CBC solver with explicit path in desktop/frozen mode when available."""
    cbc_path = _resolve_cbc_executable()
    if cbc_path:
        try:
            return pulp.PULP_CBC_CMD(msg=0, timeLimit=int(time_limit_seconds), path=cbc_path)
        except Exception:
            pass
    return pulp.PULP_CBC_CMD(msg=0, timeLimit=int(time_limit_seconds))

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def to_minutes(t: time) -> int:
    """Convert time to minutes since midnight."""
    return t.hour * 60 + t.minute


def from_minutes(mins: int) -> time:
    """Convert minutes since midnight to time."""
    mins = max(0, mins % (24 * 60))
    return time(mins // 60, mins % 60)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km between two coordinates using haversine formula."""
    if lat1 == 0 or lon1 == 0 or lat2 == 0 or lon2 == 0:
        return 999.0
    R = EARTH_RADIUS_KM
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def haversine_travel_minutes(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """Estimate travel time using haversine distance."""
    km = haversine_km(lat1, lon1, lat2, lon2)
    return max(5, int((km / FALLBACK_SPEED_KMH) * 60) + DEADHEAD_BUFFER_MINUTES)


def coords_valid(lat: float, lon: float) -> bool:
    """Check if coordinates are valid."""
    return lat != 0.0 and lon != 0.0 and -90 <= lat <= 90 and -180 <= lon <= 180


def _fallback_travel_with_connection_buffer(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """Fallback travel estimate aligned with operational connection buffer."""
    minutes = haversine_travel_minutes(lat1, lon1, lat2, lon2)
    if MIN_CONNECTION_BUFFER_MINUTES > DEADHEAD_BUFFER_MINUTES:
        minutes += MIN_CONNECTION_BUFFER_MINUTES - DEADHEAD_BUFFER_MINUTES
    return minutes


def _osrm_or_fallback_with_connection_buffer(
    src: Tuple[float, float],
    dst: Tuple[float, float],
    osrm_minutes: Optional[int],
) -> int:
    """Return travel+buffer minutes using the same policy as final feasibility checks."""
    if osrm_minutes is not None:
        return int(math.ceil(float(osrm_minutes))) + MIN_CONNECTION_BUFFER_MINUTES
    _RUNTIME_METRICS["osrm_fallback_count"] = int(_RUNTIME_METRICS.get("osrm_fallback_count", 0)) + 1
    return _fallback_travel_with_connection_buffer(src[0], src[1], dst[0], dst[1])


def _job_capacity(job: "RouteJob") -> int:
    demand_cap = int(getattr(job.route, "capacity_needed", 0) or 0)
    if demand_cap > 0:
        return max(1, demand_cap)

    stops = getattr(job.route, "stops", None) or []
    peak_from_stops = 0
    for stop in stops:
        try:
            passengers = int(getattr(stop, "passengers", 0) or 0)
        except Exception:
            passengers = 0
        if passengers > peak_from_stops:
            peak_from_stops = passengers
    if peak_from_stops > 0:
        return max(1, peak_from_stops)

    vehicle_cap_max = int(getattr(job.route, "vehicle_capacity_max", 0) or 0)
    if vehicle_cap_max > 0:
        return max(1, vehicle_cap_max)

    vehicle_cap_min = int(getattr(job.route, "vehicle_capacity_min", 0) or 0)
    if vehicle_cap_min > 0:
        return max(1, vehicle_cap_min)

    return 1


def _job_capacity_range(job: "RouteJob") -> Tuple[int, int]:
    """Return preferred seat range for a job (demand-first, range as soft constraint)."""
    cap = _job_capacity(job)
    if cap <= SMALL_SERVICE_MAX_SEATS:
        return (1, SMALL_SERVICE_MAX_SEATS)

    low = int(getattr(job.route, "vehicle_capacity_min", 0) or 0)
    high = int(getattr(job.route, "vehicle_capacity_max", 0) or 0)
    demand_margin = SMALL_BUS_CAPACITY_MAX_DIFF if cap <= SMALL_BUS_MAX_SEATS else CAPACITY_MAX_DIFF
    demand_low = max(1, cap - demand_margin)
    demand_high = cap + demand_margin

    if low > 0 and high > 0:
        rng_low = min(low, high)
        rng_high = max(low, high)
        inter_low = max(demand_low, rng_low)
        inter_high = min(demand_high, rng_high)
        if inter_low <= inter_high:
            return (inter_low, inter_high)
        return (rng_low, rng_high)

    if low > 0 and high <= 0:
        return (max(low, demand_low), max(low, demand_high))

    if high > 0 and low <= 0:
        return (min(high, demand_low), max(1, high))

    return (demand_low, demand_high)


def _is_small_service(job: "RouteJob") -> bool:
    return _job_capacity(job) <= SMALL_SERVICE_MAX_SEATS


def _capacity_bucket(capacity: int) -> int:
    if capacity <= SMALL_SERVICE_MAX_SEATS:
        return 0
    if capacity <= 20:
        return 1
    if capacity <= 35:
        return 2
    if capacity <= 50:
        return 3
    return 4


def _capacity_pair_compatible(cap_a: int, cap_b: int) -> bool:
    if cap_a <= SMALL_SERVICE_MAX_SEATS or cap_b <= SMALL_SERVICE_MAX_SEATS:
        return cap_a <= SMALL_SERVICE_MAX_SEATS and cap_b <= SMALL_SERVICE_MAX_SEATS
    a_small_bus = cap_a <= SMALL_BUS_MAX_SEATS
    b_small_bus = cap_b <= SMALL_BUS_MAX_SEATS
    # Stricter policy for small buses: do not mix with medium/large buses and
    # keep capacities close to avoid unrealistic vehicle switching.
    if a_small_bus != b_small_bus:
        return False
    if a_small_bus and b_small_bus:
        return abs(cap_a - cap_b) <= SMALL_BUS_CAPACITY_MAX_DIFF
    if (cap_a >= LARGE_ROUTE_MIN_SEATS and cap_b <= LARGE_TO_SMALL_BLOCK_SEATS) or (
        cap_b >= LARGE_ROUTE_MIN_SEATS and cap_a <= LARGE_TO_SMALL_BLOCK_SEATS
    ):
        return False
    if abs(cap_a - cap_b) > CAPACITY_MAX_DIFF:
        return False
    if abs(_capacity_bucket(cap_a) - _capacity_bucket(cap_b)) > 1:
        return False
    return True


def _jobs_capacity_compatible(job_a: "RouteJob", job_b: "RouteJob") -> bool:
    a_low, a_high = _job_capacity_range(job_a)
    b_low, b_high = _job_capacity_range(job_b)

    # Hard rule: bus should not mix routes with disjoint capacity ranges.
    ranges_overlap = not (a_high < b_low or b_high < a_low)
    if not ranges_overlap:
        return False

    return _capacity_pair_compatible(_job_capacity(job_a), _job_capacity(job_b))


def _ranges_overlap(a_low: int, a_high: int, b_low: int, b_high: int) -> bool:
    return not (a_high < b_low or b_high < a_low)


def _merge_capacity_windows(
    current: Tuple[int, int],
    incoming: Tuple[int, int],
) -> Tuple[int, int]:
    low = max(int(current[0]), int(incoming[0]))
    high = min(int(current[1]), int(incoming[1]))
    if low > high:
        return (0, 0)
    return (low, high)


def _chain_capacity_window(chain: List[int], jobs: List["RouteJob"]) -> Tuple[int, int]:
    if not chain:
        return (1, 10_000)
    low = 1
    high = 10_000
    for idx in chain:
        job_low, job_high = _job_capacity_range(jobs[idx])
        low, high = _merge_capacity_windows((low, high), (job_low, job_high))
        if low == 0 and high == 0:
            return (0, 0)
    return (low, high)


def _chain_capacity_consistent(chain: List[int], jobs: List["RouteJob"]) -> bool:
    low, high = _chain_capacity_window(chain, jobs)
    return low > 0 and high > 0 and low <= high


def _entry_arrival_min(job: "RouteJob") -> int:
    return max(
        int(job.time_minutes) - MAX_ENTRY_SHIFT_MINUTES,
        MIN_START_HOUR * 60 + int(job.duration_minutes),
    )


def _entry_arrival_max(job: "RouteJob") -> int:
    return int(job.time_minutes) + MAX_ENTRY_SHIFT_MINUTES


def _exit_departure_min(job: "RouteJob") -> int:
    return int(job.time_minutes) - MAX_EXIT_EARLY_SHIFT_MINUTES


def _exit_departure_max(job: "RouteJob") -> int:
    return int(job.time_minutes) + MAX_EXIT_LATE_SHIFT_MINUTES


def _pair_priority_bonus(job_a: "RouteJob", job_b: "RouteJob") -> float:
    bonus = 0.0
    if _is_small_service(job_a) and _is_small_service(job_b):
        # Strongly encourage clustering low-demand services (<10 students).
        bonus += 8.0
    if _job_capacity(job_a) > 55 and _job_capacity(job_b) > 55:
        # Keep large-demand services together.
        bonus += 2.0
    if getattr(job_a, "school_name", "") == getattr(job_b, "school_name", ""):
        bonus += 2.0
    cap_gap = abs(_job_capacity(job_a) - _job_capacity(job_b))
    bonus += max(0.0, 2.0 - (cap_gap / 12.0))
    return bonus


def _chain_profile(chain: List[int], jobs: List["RouteJob"]) -> Tuple[str, int, bool, int, int]:
    if not chain:
        return ("", 0, False, 0, 0)
    capacities = [_job_capacity(jobs[idx]) for idx in chain]
    school = str(getattr(jobs[chain[0]], "school_name", "") or "")
    avg_capacity = int(round(sum(capacities) / len(capacities))) if capacities else 0
    only_small_services = all(_is_small_service(jobs[idx]) for idx in chain)
    range_low, range_high = _chain_capacity_window(chain, jobs)
    if range_low == 0 and range_high == 0:
        # Inconsistent chain; expose as invalid profile.
        return (school, avg_capacity, only_small_services, 0, 0)
    return (school, avg_capacity, only_small_services, int(range_low), int(range_high))


def _profiles_capacity_compatible(
    src_profile: Tuple[str, int, bool, int, int],
    dst_profile: Tuple[str, int, bool, int, int],
) -> bool:
    _, src_capacity, _, src_low, src_high = src_profile
    _, dst_capacity, _, dst_low, dst_high = dst_profile
    if src_low <= 0 or src_high <= 0 or dst_low <= 0 or dst_high <= 0:
        return False
    if not _ranges_overlap(src_low, src_high, dst_low, dst_high):
        return False
    return _capacity_pair_compatible(max(1, src_capacity), max(1, dst_capacity))


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class RouteJob:
    """Represents a route job for optimization."""
    route: Route
    route_type: str           # "entry" or "exit"
    block: int                # 1-4
    school_name: str
    school_loc: Tuple[float, float]
    first_stop: Tuple[float, float]
    last_stop: Tuple[float, float]
    duration_minutes: int
    time_minutes: int         # arrival for entries, departure for exits
    start_loc: Tuple[float, float] = (0.0, 0.0)
    end_loc: Tuple[float, float] = (0.0, 0.0)
    scheduled_start_min: int = 0
    scheduled_end_min: int = 0
    original_index: int = 0
    valid_coords: bool = True


_LAST_OPTIMIZATION_DIAGNOSTICS: Dict[str, Any] = {
    "total_routes": 0,
    "pre_split_buses": 0,
    "best_buses": 0,
    "split_count": 0,
    "solver_status": "feasible",
    "lower_bound_buses": 0,
    "optimality_gap": 0.0,
    "avg_positioning_minutes": 0.0,
    "max_positioning_minutes": 0,
    "phase_time_sec": {},
    "pairs_total": 0,
    "pairs_pruned": 0,
    "osrm_cache_hits": 0,
    "osrm_fallback_count": 0,
}

_RUNTIME_METRICS: Dict[str, Any] = {
    "phase_time_sec": {},
    "pairs_total": 0,
    "pairs_pruned": 0,
    "osrm_fallback_count": 0,
}

_CONNECTION_TIME_CACHE: Dict[str, int] = {}


def _reset_runtime_metrics() -> None:
    _RUNTIME_METRICS["phase_time_sec"] = {}
    _RUNTIME_METRICS["pairs_total"] = 0
    _RUNTIME_METRICS["pairs_pruned"] = 0
    _RUNTIME_METRICS["osrm_fallback_count"] = 0
    _CONNECTION_TIME_CACHE.clear()


def _record_phase_time(phase_name: str, started_at: float) -> None:
    elapsed = max(0.0, time_module.perf_counter() - started_at)
    _RUNTIME_METRICS["phase_time_sec"][phase_name] = round(elapsed, 3)


def _connection_cache_key(src: Tuple[float, float], dst: Tuple[float, float]) -> str:
    return (
        f"{round(float(src[0]), 5)},{round(float(src[1]), 5)}|"
        f"{round(float(dst[0]), 5)},{round(float(dst[1]), 5)}"
    )


def _connection_minutes_cached(src: Tuple[float, float], dst: Tuple[float, float]) -> int:
    key = _connection_cache_key(src, dst)
    if key in _CONNECTION_TIME_CACHE:
        return _CONNECTION_TIME_CACHE[key]

    if not coords_valid(src[0], src[1]) or not coords_valid(dst[0], dst[1]):
        value = _fallback_travel_with_connection_buffer(src[0], src[1], dst[0], dst[1])
        _CONNECTION_TIME_CACHE[key] = value
        return value

    osrm_time = get_real_travel_time(src[0], src[1], dst[0], dst[1])
    value = _osrm_or_fallback_with_connection_buffer(src, dst, osrm_time)
    _CONNECTION_TIME_CACHE[key] = value
    return value


def get_last_optimization_diagnostics() -> Dict[str, Any]:
    """Return diagnostics for the latest optimize_v6 run."""
    return dict(_LAST_OPTIMIZATION_DIAGNOSTICS)


@dataclass
class ChainedBus:
    """A bus with chains for each time block."""
    bus_id: str = ""
    block_chains: Dict[int, List[int]] = field(default_factory=dict)  # block -> list of job indices

    def get_chain(self, block: int) -> List[int]:
        """Get chain for a specific block."""
        return self.block_chains.get(block, [])

    def set_chain(self, block: int, chain: List[int]) -> None:
        """Set chain for a specific block."""
        if chain:
            self.block_chains[block] = chain
        elif block in self.block_chains:
            del self.block_chains[block]

    def is_empty(self) -> bool:
        """Check if bus has no assigned chains."""
        return all(len(c) == 0 for c in self.block_chains.values())

    def total_routes(self) -> int:
        """Count total routes assigned to this bus."""
        return sum(len(c) for c in self.block_chains.values())

    def has_block(self, block: int) -> bool:
        """Check if bus has routes in a specific block."""
        return block in self.block_chains and len(self.block_chains[block]) > 0


# ============================================================
# PHASE 0: PREPROCESSING & VALIDATION
# ============================================================

def compute_route_duration(route: Route) -> int:
    """Compute estimated route duration in minutes."""
    if route.stops and len(route.stops) >= 2:
        osrm_duration = get_route_duration(route.stops)
        if osrm_duration is not None:
            return osrm_duration + len(route.stops)

    if route.stops:
        max_time = max((s.time_from_start for s in route.stops), default=0)
        if max_time > 0:
            return max_time

    if route.stops and len(route.stops) > 1:
        total_km = 0.0
        for i in range(len(route.stops) - 1):
            total_km += haversine_km(
                route.stops[i].lat, route.stops[i].lon,
                route.stops[i + 1].lat, route.stops[i + 1].lon
            )
        return max(15, int((total_km / FALLBACK_SPEED_KMH) * 60) + len(route.stops))

    return 30


def classify_block(route: Route) -> int:
    """Classify route into one of 4 time blocks."""
    if route.type == "entry":
        if route.arrival_time:
            mins = to_minutes(route.arrival_time)
            return 1 if mins <= MORNING_ENTRY_MAX else 3
        if route.departure_time:
            estimated_arrival = to_minutes(route.departure_time) + 30
            return 1 if estimated_arrival <= MORNING_ENTRY_MAX else 3
    elif route.type == "exit":
        if route.departure_time:
            mins = to_minutes(route.departure_time)
            return 2 if mins <= EARLY_EXIT_MAX else 4
        if route.arrival_time:
            estimated_departure = to_minutes(route.arrival_time) - 30
            return 2 if estimated_departure <= EARLY_EXIT_MAX else 4
    return 0


def validate_and_fix_stops(route: Route) -> Tuple[bool, int]:
    """Validate stop coordinates. Returns (all_valid, invalid_count)."""
    invalid = 0
    for stop in route.stops:
        if not coords_valid(stop.lat, stop.lon):
            invalid += 1
    return (invalid == 0, invalid)


def prepare_jobs(routes: List[Route]) -> Dict[int, List[RouteJob]]:
    """Prepare route jobs organized by block."""
    blocks: Dict[int, List[RouteJob]] = {1: [], 2: [], 3: [], 4: []}
    dropped: List[Route] = []
    coord_warnings = 0

    for i, route in enumerate(routes):
        block = classify_block(route)
        if block == 0:
            dropped.append(route)
            continue

        all_valid, invalid_count = validate_and_fix_stops(route)
        if invalid_count > 0:
            coord_warnings += invalid_count

        duration = compute_route_duration(route)

        if route.stops and len(route.stops) > 0:
            first_stop = (route.stops[0].lat, route.stops[0].lon)
            last_stop = (route.stops[-1].lat, route.stops[-1].lon)
        else:
            first_stop = (0.0, 0.0)
            last_stop = (0.0, 0.0)

        if route.type == "entry":
            if route.arrival_time:
                time_mins = to_minutes(route.arrival_time)
            elif route.departure_time:
                time_mins = to_minutes(route.departure_time) + duration
            else:
                time_mins = 9 * 60

            # Entry: start at pickup/origin, end at school.
            start_loc = first_stop
            end_loc = last_stop
            school_loc = end_loc
            scheduled_start_min = time_mins - duration
            scheduled_end_min = time_mins
        else:
            if route.departure_time:
                time_mins = to_minutes(route.departure_time)
            elif route.arrival_time:
                time_mins = to_minutes(route.arrival_time) - duration
            else:
                time_mins = 14 * 60

            # Exit: start at school, end at drop-off chain.
            # Source data often keeps stop order as entry-like, so we invert semantics here.
            start_loc = last_stop
            end_loc = first_stop
            school_loc = start_loc
            scheduled_start_min = time_mins
            scheduled_end_min = time_mins + duration

        job = RouteJob(
            route=route,
            route_type=route.type,
            block=block,
            school_name=route.school_name,
            school_loc=school_loc,
            first_stop=first_stop,
            last_stop=last_stop,
            duration_minutes=duration,
            time_minutes=time_mins,
            start_loc=start_loc,
            end_loc=end_loc,
            scheduled_start_min=scheduled_start_min,
            scheduled_end_min=scheduled_end_min,
            original_index=i,
            valid_coords=all_valid
        )
        blocks[block].append(job)

    if dropped:
        print(f"  WARNING: {len(dropped)} routes dropped (no time info)")
    if coord_warnings > 0:
        print(f"  WARNING: {coord_warnings} stops with invalid coordinates")

    return blocks


# ============================================================
# PHASE 1: UNIFIED TRAVEL TIME MATRIX
# ============================================================

def precompute_block_travel_matrix(
    jobs: List[RouteJob], 
    is_entry: bool
) -> Dict[Tuple[int, int], int]:
    """Precompute travel times within a block."""
    n = len(jobs)
    if n == 0:
        return {}

    # Unified operational semantics:
    # transition i -> j is always end(i) -> start(j), regardless of route type.
    sources = [job.end_loc for job in jobs]
    destinations = [job.start_loc for job in jobs]

    matrix_result = get_travel_time_matrix(sources, destinations)

    travel_times: Dict[Tuple[int, int], int] = {}
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            t = matrix_result[i][j] if matrix_result and matrix_result[i][j] is not None else None
            travel_times[(i, j)] = _osrm_or_fallback_with_connection_buffer(
                sources[i],
                destinations[j],
                t,
            )
    return travel_times


def compute_cross_block_travel(
    src_jobs: List[RouteJob], 
    src_is_entry: bool,
    dst_jobs: List[RouteJob], 
    dst_is_entry: bool
) -> Dict[Tuple[int, int], int]:
    """Compute travel times between chains of different blocks."""
    if not src_jobs or not dst_jobs:
        return {}

    # Unified operational semantics:
    # transition src -> dst is end(src) -> start(dst)
    sources = [job.end_loc for job in src_jobs]
    destinations = [job.start_loc for job in dst_jobs]

    matrix_result = get_travel_time_matrix(sources, destinations)

    travel_times: Dict[Tuple[int, int], int] = {}
    for i in range(len(src_jobs)):
        for j in range(len(dst_jobs)):
            t = matrix_result[i][j] if matrix_result and matrix_result[i][j] is not None else None
            travel_times[(i, j)] = _osrm_or_fallback_with_connection_buffer(
                sources[i],
                destinations[j],
                t,
            )
    return travel_times


# ============================================================
# PHASE 2: INTRA-BLOCK ILP OPTIMIZATION
# ============================================================

def _build_feasibility_entry(
    jobs: List[RouteJob], 
    travel_times: Dict[Tuple[int, int], int]
) -> Dict[Tuple[int, int], bool]:
    """
    Build feasibility matrix for entry routes (can shift earlier).

    For entries, route j can follow route i if:
    - Route i arrives at school_i at some time a_i in [time_i - MAX_EARLY, time_i]
    - Bus travels tt from school_i to first_stop_j
    - Bus runs route j (duration_j), arriving at school_j at a_j = a_i + tt + duration_j
    - a_j must be in [time_j - MAX_EARLY, time_j]

    The BEST CASE is when route i is maximally shifted early:
    a_i = time_i - MAX_EARLY -> a_j = (time_i - MAX_EARLY) + tt + duration_j
    This must be <= time_j.

    The WORST CASE is no shift: a_i = time_i -> a_j = time_i + tt + duration_j <= time_j.
    """
    n = len(jobs)
    feasible: Dict[Tuple[int, int], bool] = {}
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if not _jobs_capacity_compatible(jobs[i], jobs[j]):
                continue
            tt = travel_times.get((i, j), 999)

            # Best case: i arrives as early as possible
            earliest_i = _entry_arrival_min(jobs[i])
            # Earliest possible arrival at school_j
            earliest_j = earliest_i + tt + jobs[j].duration_minutes
            # Must be within j's time window
            if earliest_j <= _entry_arrival_max(jobs[j]):
                feasible[(i, j)] = True
    return feasible


def _build_feasibility_exit(
    jobs: List[RouteJob], 
    travel_times: Dict[Tuple[int, int], int]
) -> Dict[Tuple[int, int], bool]:
    """Build feasibility matrix for exit routes (-5/+10 min departure shift)."""
    n = len(jobs)
    feasible: Dict[Tuple[int, int], bool] = {}
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if not _jobs_capacity_compatible(jobs[i], jobs[j]):
                continue
            tt = travel_times.get((i, j), 999)
            earliest_end_i = _exit_departure_min(jobs[i]) + jobs[i].duration_minutes
            latest_start_j = _exit_departure_max(jobs[j])
            if earliest_end_i + tt <= latest_start_j:
                feasible[(i, j)] = True
    return feasible


def _compute_ml_pair_scores(
    jobs: List[RouteJob],
    travel_times: Dict[Tuple[int, int], int],
    is_entry: bool,
) -> Dict[Tuple[int, int], float]:
    """
    Compute ML compatibility score per pair (i, j).

    If ML scorer is unavailable, gracefully fall back to neutral scores.
    """
    try:
        try:
            from services.ml_assignment_service import build_ml_pair_scores
        except ImportError:
            from backend.services.ml_assignment_service import build_ml_pair_scores

        return build_ml_pair_scores(
            jobs,
            travel_times,
            is_entry=is_entry,
            min_buffer_minutes=float(MIN_CONNECTION_BUFFER_MINUTES),
            max_early_arrival_minutes=int(MAX_ENTRY_SHIFT_MINUTES),
            max_exit_shift_minutes=int(MAX_EXIT_LATE_SHIFT_MINUTES),
            min_start_hour=int(MIN_START_HOUR),
        )
    except Exception as exc:
        logger.warning("ML pair scoring unavailable, using heuristic-only assignment: %s", exc)
        return {}


def build_chains_ilp(
    jobs: List[RouteJob], 
    travel_times: Dict[Tuple[int, int], int], 
    is_entry: bool,
    pair_scores: Optional[Dict[Tuple[int, int], float]] = None,
) -> Optional[List[List[int]]]:
    """
    Build optimal chains using ILP minimum path cover with time tracking.

    For entries: uses continuous time variables to properly model the cascading
    early-arrival shifts. This avoids the transitivity issue where pairwise
    feasibility doesn't guarantee chain feasibility.
    """
    n = len(jobs)
    if n == 0:
        return []
    if n == 1:
        return [[0]]

    # Build feasibility
    if is_entry:
        feasible = _build_feasibility_entry(jobs, travel_times)
    else:
        feasible = _build_feasibility_exit(jobs, travel_times)

    if not feasible:
        return [[i] for i in range(n)]

    # ILP: Minimum Path Cover with Time Tracking
    prob = pulp.LpProblem("MinChains", pulp.LpMinimize)

    # x[i][j] = 1 if j follows i on the same bus
    x: Dict[Tuple[int, int], Any] = {}
    for (i, j) in feasible:
        x[(i, j)] = pulp.LpVariable(f"x_{i}_{j}", cat='Binary')

    # y[i] = 1 if i starts a new chain
    y = {i: pulp.LpVariable(f"y_{i}", cat='Binary') for i in range(n)}

    if is_entry:
        # a[i] = actual arrival time at school for route i (continuous)
        BIG_M = 24 * 60  # Big-M constant
        a: Dict[int, Any] = {}
        for i in range(n):
            lo = _entry_arrival_min(jobs[i])
            hi = _entry_arrival_max(jobs[i])
            a[i] = pulp.LpVariable(f"a_{i}", lowBound=lo, upBound=hi, cat='Continuous')

        # Time linking constraints: if x[i][j] = 1 then a[j] >= a[i] + tt + duration_j
        for (i, j) in feasible:
            tt = travel_times.get((i, j), 999)
            needed = tt + jobs[j].duration_minutes
            # a[j] >= a[i] + needed - BIG_M * (1 - x[i][j])
            prob += a[j] >= a[i] + needed - BIG_M * (1 - x[(i, j)])
    else:  # exits - con variables de tiempo
        BIG_M = 24 * 60
        d: Dict[int, Any] = {}
        for i in range(n):
            lo = _exit_departure_min(jobs[i])
            hi = _exit_departure_max(jobs[i])
            d[i] = pulp.LpVariable(f"d_{i}", lowBound=lo, upBound=hi, cat='Continuous')
        for (i, j) in feasible:
            tt = travel_times.get((i, j), 999)
            prob += d[j] >= d[i] + jobs[i].duration_minutes + tt - BIG_M * (1 - x[(i, j)])

    # Minimize chain starts (primary) + penalize weak ML links (secondary).
    # Primary term dominates to preserve minimum-bus objective.
    primary = pulp.lpSum(y[i] for i in range(n))
    if pair_scores:
        secondary = pulp.lpSum(
            ((1.0 - float(pair_scores.get((i, j), 0.5))) - (0.08 * _pair_priority_bonus(jobs[i], jobs[j]))) * x[(i, j)]
            for (i, j) in x
        )
    else:
        secondary = 0.0
    prob += (10000.0 * primary) + secondary

    # Each route has at most one predecessor
    for j in range(n):
        preds = [x[(i, j)] for i in range(n) if (i, j) in x]
        if preds:
            prob += pulp.lpSum(preds) <= 1
            prob += y[j] >= 1 - pulp.lpSum(preds)
        else:
            prob += y[j] == 1

    # Each route has at most one successor
    for i in range(n):
        succs = [x[(i, j)] for j in range(n) if (i, j) in x]
        if succs:
            prob += pulp.lpSum(succs) <= 1

    # Solve
    solver = _build_cbc_solver(ILP_TIME_LIMIT)
    prob.solve(solver)

    if prob.status != pulp.constants.LpStatusOptimal:
        print(f"    ILP solver did not find optimal (status={prob.status}), falling back to greedy")
        return None

    # Extract chains
    successor: Dict[int, int] = {}
    for (i, j), var in x.items():
        if var.value() is not None and var.value() > 0.5:
            successor[i] = j

    has_pred = set(successor.values())
    chains: List[List[int]] = []
    for start in range(n):
        if start not in has_pred:
            chain = [start]
            current = start
            while current in successor:
                current = successor[current]
                chain.append(current)
            chains.append(chain)

    return chains


def build_chains_greedy(
    jobs: List[RouteJob], 
    travel_times: Dict[Tuple[int, int], int], 
    is_entry: bool,
    pair_scores: Optional[Dict[Tuple[int, int], float]] = None,
) -> List[List[int]]:
    """Enhanced greedy chain building with many seeding strategies."""
    n = len(jobs)
    if n == 0:
        return []

    best_chains: Optional[List[List[int]]] = None
    best_count = float('inf')

    # Strategy 1: earliest first
    strategies: List[List[int]] = [
        sorted(range(n), key=lambda i: jobs[i].time_minutes),
    ]
    # Strategy 2: latest first
    strategies.append(sorted(range(n), key=lambda i: -jobs[i].time_minutes))

    # Strategy 3: most-connected first
    connectivity: Dict[int, int] = {}
    for i in range(n):
        count = 0
        for j in range(n):
            if i == j:
                continue
            if not _jobs_capacity_compatible(jobs[i], jobs[j]):
                continue
            tt = travel_times.get((i, j), 999)
            if is_entry:
                earliest_i = _entry_arrival_min(jobs[i])
                can_reach = earliest_i + tt + jobs[j].duration_minutes <= _entry_arrival_max(jobs[j])
            else:
                earliest_end_i = _exit_departure_min(jobs[i]) + jobs[i].duration_minutes
                latest_start_j = _exit_departure_max(jobs[j])
                can_reach = earliest_end_i + tt <= latest_start_j
            if can_reach:
                count += 1
        connectivity[i] = count
    strategies.append(sorted(range(n), key=lambda i: -connectivity.get(i, 0)))

    # Strategy 4: least-connected first (hard-to-chain routes first)
    strategies.append(sorted(range(n), key=lambda i: connectivity.get(i, 0)))

    # Strategy 5: by school name (group similar routes)
    strategies.append(sorted(range(n), key=lambda i: (jobs[i].school_name, jobs[i].time_minutes)))

    # Strategy 6: random-ish (by duration, longest first)
    strategies.append(sorted(range(n), key=lambda i: -jobs[i].duration_minutes))

    # Strategy 7: by geographic position (lat+lon hash for spatial ordering)
    strategies.append(sorted(range(n), key=lambda i: (jobs[i].school_loc[0] + jobs[i].school_loc[1])))

    for seed_order in strategies:
        if is_entry:
            chains = _greedy_chain_entries(jobs, travel_times, seed_order, pair_scores=pair_scores)
        else:
            chains = _greedy_chain_exits(jobs, travel_times, seed_order, pair_scores=pair_scores)
        if len(chains) < best_count:
            best_count = len(chains)
            best_chains = chains

    return best_chains if best_chains is not None else []


def _greedy_chain_entries(
    jobs: List[RouteJob], 
    travel_times: Dict[Tuple[int, int], int], 
    seed_order: List[int],
    pair_scores: Optional[Dict[Tuple[int, int], float]] = None,
) -> List[List[int]]:
    """Greedy chain builder for entry routes."""
    n = len(jobs)
    assigned: Set[int] = set()
    chains: List[List[int]] = []

    for seed_idx in seed_order:
        if seed_idx in assigned:
            continue
        chain = [seed_idx]
        assigned.add(seed_idx)

        current_arrival = _entry_arrival_min(jobs[seed_idx])
        route_start = current_arrival - jobs[seed_idx].duration_minutes
        if route_start < MIN_START_HOUR * 60:
            current_arrival = MIN_START_HOUR * 60 + jobs[seed_idx].duration_minutes
        current_arrival = min(current_arrival, _entry_arrival_max(jobs[seed_idx]))

        while True:
            best_next: Optional[int] = None
            best_score = float('inf')
            best_arrival = 0

            for j in range(n):
                if j in assigned:
                    continue
                if not _jobs_capacity_compatible(jobs[chain[-1]], jobs[j]):
                    continue
                tt = travel_times.get((chain[-1], j), 999)
                arrival_at_first = current_arrival + tt
                min_eff = arrival_at_first + jobs[j].duration_minutes
                max_eff = _entry_arrival_max(jobs[j])
                if min_eff > max_eff:
                    continue
                effective = max(min_eff, _entry_arrival_min(jobs[j]))
                effective = min(effective, max_eff)
                deadhead = tt
                wasted = max(0, (effective - jobs[j].duration_minutes) - arrival_at_first)
                ml_score = float(pair_scores.get((chain[-1], j), 0.5)) if pair_scores else 0.5
                priority_bonus = _pair_priority_bonus(jobs[chain[-1]], jobs[j])
                score = deadhead * 2 + wasted - (ml_score * 6.0) - (priority_bonus * 4.0)
                if score < best_score:
                    best_score = score
                    best_next = j
                    best_arrival = effective

            if best_next is not None:
                chain.append(best_next)
                assigned.add(best_next)
                current_arrival = best_arrival
            else:
                break
        chains.append(chain)
    return chains


def _greedy_chain_exits(
    jobs: List[RouteJob],
    travel_times: Dict[Tuple[int, int], int],
    seed_order: List[int],
    pair_scores: Optional[Dict[Tuple[int, int], float]] = None,
) -> List[List[int]]:
    """Greedy chain builder for exit routes with -5/+10 min shift flexibility."""
    n = len(jobs)
    assigned: Set[int] = set()
    chains: List[List[int]] = []

    for seed_idx in seed_order:
        if seed_idx in assigned:
            continue
        chain = [seed_idx]
        assigned.add(seed_idx)
        current_end = _exit_departure_min(jobs[seed_idx]) + jobs[seed_idx].duration_minutes

        while True:
            best_next: Optional[int] = None
            best_score = float('inf')

            for j in range(n):
                if j in assigned:
                    continue
                if not _jobs_capacity_compatible(jobs[chain[-1]], jobs[j]):
                    continue
                tt = travel_times.get((chain[-1], j), 999)
                arrival = current_end + tt
                if arrival > _exit_departure_max(jobs[j]):
                    continue
                effective_departure = max(_exit_departure_min(jobs[j]), arrival)
                effective_departure = min(effective_departure, _exit_departure_max(jobs[j]))
                wait = effective_departure - arrival
                ml_score = float(pair_scores.get((chain[-1], j), 0.5)) if pair_scores else 0.5
                priority_bonus = _pair_priority_bonus(jobs[chain[-1]], jobs[j])
                score = tt * 2 + wait - (ml_score * 6.0) - (priority_bonus * 4.0)
                if score < best_score:
                    best_score = score
                    best_next = j

            if best_next is not None:
                chain.append(best_next)
                assigned.add(best_next)
                tt = travel_times.get((chain[-2], best_next), 999)
                arrival = current_end + tt
                effective_departure = max(_exit_departure_min(jobs[best_next]), arrival)
                effective_departure = min(effective_departure, _exit_departure_max(jobs[best_next]))
                current_end = effective_departure + jobs[best_next].duration_minutes
            else:
                break
        chains.append(chain)
    return chains


def _split_chain_by_capacity_window(chain: List[int], jobs: List[RouteJob]) -> List[List[int]]:
    """Split a chain when adding a route breaks bus-wide capacity-range consistency."""
    if not chain:
        return []
    result: List[List[int]] = []
    current: List[int] = []
    current_window: Tuple[int, int] = (1, 10_000)
    for idx in chain:
        route_window = _job_capacity_range(jobs[idx])
        merged = _merge_capacity_windows(current_window, route_window)
        if current and merged == (0, 0):
            result.append(current)
            current = [idx]
            current_window = route_window
            continue
        current.append(idx)
        current_window = merged
    if current:
        result.append(current)
    return result


def _normalize_chains_capacity(chains: List[List[int]], jobs: List[RouteJob]) -> List[List[int]]:
    """Ensure every chain has a non-empty common capacity range."""
    normalized: List[List[int]] = []
    for chain in chains:
        normalized.extend(_split_chain_by_capacity_window(chain, jobs))
    return normalized

def build_block_chains(
    jobs: List[RouteJob], 
    travel_times: Dict[Tuple[int, int], int], 
    is_entry: bool, 
    block_name: str,
    use_ml_assignment: bool = True,
) -> List[List[int]]:
    """
    Build chains for a block.

    Strategy:
    - For entries: use enhanced greedy with more strategies (ILP with time
      constraints is too slow for 90+ routes and doesn't beat greedy)
    - For exits: try ILP minimum path cover (no time constraints needed since
      exits have fixed departure times, so pairwise feasibility IS transitive)
    """
    if not jobs:
        return []

    pair_scores: Dict[Tuple[int, int], float] = {}
    if use_ml_assignment:
        pair_scores = _compute_ml_pair_scores(jobs, travel_times, is_entry)
    greedy_chains = build_chains_greedy(jobs, travel_times, is_entry, pair_scores=pair_scores)

    if not is_entry:
        # For exits, try ILP - pairwise feasibility IS transitive
        ilp_chains = build_chains_ilp(jobs, travel_times, is_entry, pair_scores=pair_scores)
        if ilp_chains is not None and len(ilp_chains) <= len(greedy_chains):
            normalized_ilp = _normalize_chains_capacity(ilp_chains, jobs)
            if len(normalized_ilp) != len(ilp_chains):
                print(f"    {block_name}: capacity normalization split {len(ilp_chains)} -> {len(normalized_ilp)}")
            print(f"    {block_name}: ILP={len(normalized_ilp)} chains vs Greedy={len(greedy_chains)} (using ILP)")
            return normalized_ilp
        elif ilp_chains is not None:
            print(f"    {block_name}: ILP={len(ilp_chains)} vs Greedy={len(greedy_chains)} (using Greedy)")
        else:
            print(f"    {block_name}: ILP failed, Greedy={len(greedy_chains)} chains")
        normalized_greedy = _normalize_chains_capacity(greedy_chains, jobs)
        if len(normalized_greedy) != len(greedy_chains):
            print(f"    {block_name}: capacity normalization split {len(greedy_chains)} -> {len(normalized_greedy)}")
        return normalized_greedy
    else:
        normalized_greedy = _normalize_chains_capacity(greedy_chains, jobs)
        if len(normalized_greedy) != len(greedy_chains):
            print(f"    {block_name}: capacity normalization split {len(greedy_chains)} -> {len(normalized_greedy)}")
        print(f"    {block_name}: Greedy={len(normalized_greedy)} chains")
        return normalized_greedy


# ============================================================
# PHASE 3: CROSS-BLOCK ILP MATCHING
# ============================================================

def _get_chain_end_info(
    chain: List[int], 
    jobs: List[RouteJob], 
    is_entry: bool
) -> Tuple[int, Tuple[float, float]]:
    """Get end time and location for a chain."""
    last_job = jobs[chain[-1]]
    if is_entry:
        return (_entry_arrival_max(last_job), last_job.end_loc)
    else:
        return (_exit_departure_max(last_job) + last_job.duration_minutes, last_job.end_loc)


def _get_chain_start_info(
    chain: List[int], 
    jobs: List[RouteJob], 
    is_entry: bool
) -> Tuple[int, Tuple[float, float]]:
    """Get start time and location for a chain."""
    first_job = jobs[chain[0]]
    if is_entry:
        earliest = _entry_arrival_min(first_job) - first_job.duration_minutes
        return (earliest, first_job.start_loc)
    else:
        return (_exit_departure_min(first_job), first_job.start_loc)


def match_blocks_ilp(
    chains_a_ends: List[Tuple[int, Tuple[float, float]]],
    chains_b_starts: List[Tuple[int, Tuple[float, float]]],
    source_meta: Optional[List[Tuple[str, int, bool, int, int]]] = None,
    target_meta: Optional[List[Tuple[str, int, bool, int, int]]] = None,
) -> List[Tuple[int, int]]:
    """Find maximum cross-block matching with timing, OSRM, school and capacity affinity."""
    na = len(chains_a_ends)
    nb = len(chains_b_starts)
    if na == 0 or nb == 0:
        return []

    source_meta = source_meta or [("", 0, False, 0, 0) for _ in range(na)]
    target_meta = target_meta or [("", 0, False, 0, 0) for _ in range(nb)]

    total_pairs = na * nb
    candidate_pairs: List[Tuple[int, int]] = []
    src_idx_for_matrix: Set[int] = set()
    dst_idx_for_matrix: Set[int] = set()

    for i in range(na):
        end_t, end_loc = chains_a_ends[i]
        _, src_capacity, _, src_low, src_high = source_meta[i]
        for j in range(nb):
            start_t, start_loc = chains_b_starts[j]
            _, dst_capacity, _, dst_low, dst_high = target_meta[j]

            if src_low <= 0 or src_high <= 0 or dst_low <= 0 or dst_high <= 0:
                continue
            if not _ranges_overlap(src_low, src_high, dst_low, dst_high):
                continue
            if not _capacity_pair_compatible(max(1, src_capacity), max(1, dst_capacity)):
                continue

            # Fast timing prune: any movement requires at least connection buffer.
            if end_t + MIN_CONNECTION_BUFFER_MINUTES > start_t + CROSS_BLOCK_FLEX_MINUTES:
                continue

            candidate_pairs.append((i, j))
            if coords_valid(end_loc[0], end_loc[1]) and coords_valid(start_loc[0], start_loc[1]):
                src_idx_for_matrix.add(i)
                dst_idx_for_matrix.add(j)

    if not candidate_pairs:
        _RUNTIME_METRICS["pairs_total"] = int(_RUNTIME_METRICS.get("pairs_total", 0)) + total_pairs
        _RUNTIME_METRICS["pairs_pruned"] = int(_RUNTIME_METRICS.get("pairs_pruned", 0)) + total_pairs
        return []

    matrix_lookup: Dict[Tuple[int, int], Optional[int]] = {}
    if src_idx_for_matrix and dst_idx_for_matrix:
        src_order = sorted(src_idx_for_matrix)
        dst_order = sorted(dst_idx_for_matrix)
        src_coords = [chains_a_ends[idx][1] for idx in src_order]
        dst_coords = [chains_b_starts[idx][1] for idx in dst_order]
        matrix = get_travel_time_matrix(src_coords, dst_coords)
        for r, src_idx in enumerate(src_order):
            for c, dst_idx in enumerate(dst_order):
                matrix_lookup[(src_idx, dst_idx)] = matrix[r][c]

    feasible: Dict[Tuple[int, int], int] = {}
    pair_value: Dict[Tuple[int, int], float] = {}
    for i, j in candidate_pairs:
        end_t, end_loc = chains_a_ends[i]
        src_school, src_capacity, src_small, src_low, src_high = source_meta[i]
        start_t, start_loc = chains_b_starts[j]
        dst_school, dst_capacity, dst_small, dst_low, dst_high = target_meta[j]

        if not coords_valid(end_loc[0], end_loc[1]) or not coords_valid(start_loc[0], start_loc[1]):
            tt = _fallback_travel_with_connection_buffer(end_loc[0], end_loc[1], start_loc[0], start_loc[1])
        else:
            osrm_time = matrix_lookup.get((i, j))
            tt = _osrm_or_fallback_with_connection_buffer(end_loc, start_loc, osrm_time)

        if end_t + tt > start_t + CROSS_BLOCK_FLEX_MINUTES:
            continue

        if src_low <= 0 or src_high <= 0 or dst_low <= 0 or dst_high <= 0:
            continue
        if not _ranges_overlap(src_low, src_high, dst_low, dst_high):
            continue
        if not _capacity_pair_compatible(max(1, src_capacity), max(1, dst_capacity)):
            continue

        gap = start_t - (end_t + tt)
        feasible[(i, j)] = gap
        bonus = 0.0
        if src_school and dst_school and src_school == dst_school:
            bonus += CROSS_BLOCK_SCHOOL_BONUS
        bonus += CROSS_BLOCK_CAPACITY_BONUS
        if src_small and dst_small:
            bonus += CROSS_BLOCK_SMALL_SERVICE_BONUS
        pair_value[(i, j)] = bonus

    _RUNTIME_METRICS["pairs_total"] = int(_RUNTIME_METRICS.get("pairs_total", 0)) + total_pairs
    _RUNTIME_METRICS["pairs_pruned"] = int(_RUNTIME_METRICS.get("pairs_pruned", 0)) + max(
        0, total_pairs - len(feasible)
    )

    if not feasible:
        return []

    prob = pulp.LpProblem("MaxMatch", pulp.LpMaximize)
    m: Dict[Tuple[int, int], Any] = {}
    for (i, j) in feasible:
        m[(i, j)] = pulp.LpVariable(f"m_{i}_{j}", cat='Binary')

    max_gap = max(feasible.values()) + 1 if feasible else 1
    prob += pulp.lpSum(
        m[(i, j)] * (1000.0 + (max_gap - feasible[(i, j)]) + pair_value.get((i, j), 0.0))
        for (i, j) in feasible
    )

    for i in range(na):
        relevant = [m[(i, j)] for j in range(nb) if (i, j) in m]
        if relevant:
            prob += pulp.lpSum(relevant) <= 1
    for j in range(nb):
        relevant = [m[(i, j)] for i in range(na) if (i, j) in m]
        if relevant:
            prob += pulp.lpSum(relevant) <= 1

    solver = _build_cbc_solver(10)
    prob.solve(solver)

    pairs: List[Tuple[int, int]] = []
    for (i, j), var in m.items():
        if var.value() is not None and var.value() > 0.5:
            pairs.append((i, j))

    return pairs

def merge_all_blocks(
    block_chains: Dict[int, List[List[int]]],
    block_jobs: Dict[int, List[RouteJob]],
) -> List[ChainedBus]:
    """Merge chains across all 4 blocks using sequential ILP matching."""

    buses: List[ChainedBus] = []

    b1_chains = block_chains.get(1, [])
    b2_chains = block_chains.get(2, [])
    b3_chains = block_chains.get(3, [])
    b4_chains = block_chains.get(4, [])

    b1_jobs = block_jobs.get(1, [])
    b2_jobs = block_jobs.get(2, [])
    b3_jobs = block_jobs.get(3, [])
    b4_jobs = block_jobs.get(4, [])

    # Step 1: Initialize with block1 chains
    for chain in b1_chains:
        bus = ChainedBus()
        bus.set_chain(1, chain)
        buses.append(bus)

    # Step 2: Match block1 -> block2
    if b1_chains and b2_chains:
        ends_1 = [_get_chain_end_info(c, b1_jobs, True) for c in b1_chains]
        starts_2 = [_get_chain_start_info(c, b2_jobs, False) for c in b2_chains]
        meta_1 = [_chain_profile(c, b1_jobs) for c in b1_chains]
        meta_2 = [_chain_profile(c, b2_jobs) for c in b2_chains]
        pairs_12 = match_blocks_ilp(ends_1, starts_2, source_meta=meta_1, target_meta=meta_2)
        matched_b2: Set[int] = set()
        for (a_idx, b_idx) in pairs_12:
            buses[a_idx].set_chain(2, b2_chains[b_idx])
            matched_b2.add(b_idx)
        # Unmatched block2 -> new buses
        for j, chain in enumerate(b2_chains):
            if j not in matched_b2:
                bus = ChainedBus()
                bus.set_chain(2, chain)
                buses.append(bus)
        print(f"    Block1->Block2: {len(pairs_12)} matched, {len(b2_chains) - len(pairs_12)} new buses")
    elif b2_chains:
        for chain in b2_chains:
            bus = ChainedBus()
            bus.set_chain(2, chain)
            buses.append(bus)

    # Step 3: Match existing buses -> block3
    if b3_chains:
        bus_ends: List[Tuple[int, Tuple[float, float]]] = []
        bus_indices: List[int] = []
        for bi, bus in enumerate(buses):
            latest_end = _get_bus_latest_end(bus, block_jobs)
            if latest_end[0] is not None and latest_end[1] is not None:
                bus_ends.append((latest_end[0], latest_end[1]))
                bus_indices.append(bi)

        starts_3 = [_get_chain_start_info(c, b3_jobs, True) for c in b3_chains]
        bus_meta = [_get_bus_latest_profile(buses[bi], block_jobs) for bi in bus_indices]
        meta_3 = [_chain_profile(c, b3_jobs) for c in b3_chains]
        pairs_b3 = match_blocks_ilp(bus_ends, starts_3, source_meta=bus_meta, target_meta=meta_3)
        matched_b3: Set[int] = set()
        for (a_idx, b_idx) in pairs_b3:
            real_bus_idx = bus_indices[a_idx]
            buses[real_bus_idx].set_chain(3, b3_chains[b_idx])
            matched_b3.add(b_idx)
        for j, chain in enumerate(b3_chains):
            if j not in matched_b3:
                bus = ChainedBus()
                bus.set_chain(3, chain)
                buses.append(bus)
        print(f"    Buses->Block3: {len(pairs_b3)} matched, {len(b3_chains) - len(pairs_b3)} new buses")

    # Step 4: Match existing buses -> block4
    if b4_chains:
        bus_ends = []
        bus_indices = []
        for bi, bus in enumerate(buses):
            latest_end = _get_bus_latest_end(bus, block_jobs)
            if latest_end[0] is not None and latest_end[1] is not None:
                bus_ends.append((latest_end[0], latest_end[1]))
                bus_indices.append(bi)

        starts_4 = [_get_chain_start_info(c, b4_jobs, False) for c in b4_chains]
        bus_meta = [_get_bus_latest_profile(buses[bi], block_jobs) for bi in bus_indices]
        meta_4 = [_chain_profile(c, b4_jobs) for c in b4_chains]
        pairs_b4 = match_blocks_ilp(bus_ends, starts_4, source_meta=bus_meta, target_meta=meta_4)
        matched_b4: Set[int] = set()
        for (a_idx, b_idx) in pairs_b4:
            real_bus_idx = bus_indices[a_idx]
            buses[real_bus_idx].set_chain(4, b4_chains[b_idx])
            matched_b4.add(b_idx)
        for j, chain in enumerate(b4_chains):
            if j not in matched_b4:
                bus = ChainedBus()
                bus.set_chain(4, chain)
                buses.append(bus)
        print(f"    Buses->Block4: {len(pairs_b4)} matched, {len(b4_chains) - len(pairs_b4)} new buses")

    # Step 5: Consolidation - try to absorb single-block buses
    buses = _consolidate_buses(buses, block_jobs)

    return buses


def _get_bus_latest_end(
    bus: ChainedBus, 
    block_jobs: Dict[int, List[RouteJob]]
) -> Tuple[Optional[int], Optional[Tuple[float, float]]]:
    """Get the latest end time and location across all blocks of a bus."""
    latest_time: Optional[int] = None
    latest_loc: Optional[Tuple[float, float]] = None

    for block in [4, 3, 2, 1]:
        chain = bus.get_chain(block)
        if chain:
            jobs = block_jobs.get(block, [])
            if not jobs:
                continue
            is_entry = block in (1, 3)
            end_t, end_loc = _get_chain_end_info(chain, jobs, is_entry)
            if latest_time is None or end_t > latest_time:
                latest_time = end_t
                latest_loc = end_loc

    return (latest_time, latest_loc)


def _get_bus_latest_profile(
    bus: ChainedBus,
    block_jobs: Dict[int, List[RouteJob]],
) -> Tuple[str, int, bool, int, int]:
    """Get school/capacity profile of the latest block assigned to a bus."""
    for block in [4, 3, 2, 1]:
        chain = bus.get_chain(block)
        if chain:
            jobs = block_jobs.get(block, [])
            if jobs:
                return _chain_profile(chain, jobs)
    return ("", 0, False, 0, 0)


def _get_bus_capacity_window(
    bus: ChainedBus,
    block_jobs: Dict[int, List[RouteJob]],
) -> Tuple[int, int]:
    """Capacity window intersection across all routes assigned to a bus."""
    low = 1
    high = 10_000
    has_routes = False
    for block in [1, 2, 3, 4]:
        chain = bus.get_chain(block)
        if not chain:
            continue
        jobs = block_jobs.get(block, [])
        if not jobs:
            continue
        has_routes = True
        block_low, block_high = _chain_capacity_window(chain, jobs)
        if block_low == 0 and block_high == 0:
            return (0, 0)
        low, high = _merge_capacity_windows((low, high), (block_low, block_high))
        if low == 0 and high == 0:
            return (0, 0)
    if not has_routes:
        return (1, 10_000)
    return (low, high)


def _consolidate_buses(
    buses: List[ChainedBus], 
    block_jobs: Dict[int, List[RouteJob]]
) -> List[ChainedBus]:
    """Try to merge single-block buses into multi-block buses."""
    merged_away: Set[int] = set()

    for pass_num in range(5):
        progress = False
        for src_idx in range(len(buses)):
            if src_idx in merged_away:
                continue
            src = buses[src_idx]

            # Try merging buses with only one block into other buses
            src_blocks = [b for b in [1, 2, 3, 4] if src.has_block(b)]
            if len(src_blocks) >= 3:
                continue  # Already well-utilized

            for block in src_blocks:
                chain = src.get_chain(block)
                if not chain:
                    continue

                jobs = block_jobs.get(block, [])
                if not jobs:
                    continue
                src_profile = _chain_profile(chain, jobs)

                is_entry = block in (1, 3)
                chain_start_t, chain_start_loc = _get_chain_start_info(chain, jobs, is_entry)

                best_target: Optional[Tuple[int, str]] = None
                best_gap = float('inf')

                for tgt_idx in range(len(buses)):
                    if tgt_idx in merged_away or tgt_idx == src_idx:
                        continue
                    tgt = buses[tgt_idx]
                    tgt_bus_window = _get_bus_capacity_window(tgt, block_jobs)
                    src_chain_window = _chain_capacity_window(chain, jobs)
                    if src_chain_window == (0, 0):
                        continue
                    if not _ranges_overlap(tgt_bus_window[0], tgt_bus_window[1], src_chain_window[0], src_chain_window[1]):
                        continue

                    if tgt.has_block(block):
                        # Target already has this block - try appending
                        tgt_chain = tgt.get_chain(block)
                        if not _chain_capacity_consistent(tgt_chain + chain, jobs):
                            continue
                        tgt_end_t, tgt_end_loc = _get_chain_end_info(tgt_chain, jobs, is_entry)

                        tt = _connection_minutes_cached(tgt_end_loc, chain_start_loc)

                        if tgt_end_t + tt <= chain_start_t + CROSS_BLOCK_FLEX_MINUTES:
                            gap = chain_start_t - (tgt_end_t + tt)
                            if gap < best_gap:
                                best_gap = gap
                                best_target = (tgt_idx, "append")
                    else:
                        # Target doesn't have this block - check timing from its latest end
                        tgt_latest = _get_bus_latest_end(tgt, block_jobs)
                        if tgt_latest[0] is None or tgt_latest[1] is None:
                            continue
                        tgt_profile = _get_bus_latest_profile(tgt, block_jobs)
                        if not _profiles_capacity_compatible(tgt_profile, src_profile):
                            continue

                        if tgt_latest[0] >= chain_start_t:
                            continue

                        tt = _connection_minutes_cached(tgt_latest[1], chain_start_loc)

                        if tgt_latest[0] + tt <= chain_start_t + CROSS_BLOCK_FLEX_MINUTES:
                            gap = chain_start_t - (tgt_latest[0] + tt)
                            if gap < best_gap:
                                best_gap = gap
                                best_target = (tgt_idx, "set")

                if best_target is not None:
                    tgt_idx, mode = best_target
                    tgt = buses[tgt_idx]
                    if mode == "append":
                        tgt.set_chain(block, tgt.get_chain(block) + chain)
                    else:
                        tgt.set_chain(block, chain)
                    src.set_chain(block, [])

                    if src.is_empty():
                        merged_away.add(src_idx)
                        progress = True
                        break

        if not progress:
            break

    result = [b for i, b in enumerate(buses) if i not in merged_away]
    if merged_away:
        print(f"    Consolidation: absorbed {len(merged_away)} buses over {pass_num + 1} passes")
    return result


# ============================================================
# PHASE 4: LOCAL SEARCH IMPROVEMENT
# ============================================================

def _can_append_to_chain_entry(
    chain: List[int],
    job_idx: int,
    jobs: List[RouteJob],
    travel_times: Dict[Tuple[int, int], int]
) -> bool:
    """Check if job_idx can be appended to an entry chain."""
    if not chain:
        return True
    last = chain[-1]
    if not _jobs_capacity_compatible(jobs[last], jobs[job_idx]):
        return False
    return _verify_entry_chain(chain + [job_idx], jobs, travel_times)


def _can_prepend_to_chain_entry(
    chain: List[int],
    job_idx: int,
    jobs: List[RouteJob],
    travel_times: Dict[Tuple[int, int], int]
) -> bool:
    """Check if job_idx can be prepended to an entry chain."""
    if not chain:
        return True
    if not _jobs_capacity_compatible(jobs[job_idx], jobs[chain[0]]):
        return False
    return _verify_entry_chain([job_idx] + chain, jobs, travel_times)


def _can_append_to_chain_exit(
    chain: List[int],
    job_idx: int,
    jobs: List[RouteJob],
    travel_times: Dict[Tuple[int, int], int]
) -> bool:
    """Check if job_idx can be appended to an exit chain with -5/+10 shift."""
    if not chain:
        return True
    last = chain[-1]
    if not _jobs_capacity_compatible(jobs[last], jobs[job_idx]):
        return False
    return _verify_exit_chain(chain + [job_idx], jobs, travel_times)


def _verify_entry_chain(
    chain: List[int],
    jobs: List[RouteJob],
    tt: Dict[Tuple[int, int], int]
) -> bool:
    """Verify an entry chain is feasible with +/-5 min arrival shifts."""
    if len(chain) <= 1:
        return True
    if not _chain_capacity_consistent(chain, jobs):
        return False

    first = jobs[chain[0]]
    current_arrival = _entry_arrival_min(first)
    if current_arrival > _entry_arrival_max(first):
        return False

    for i in range(1, len(chain)):
        prev_job = jobs[chain[i - 1]]
        next_job = jobs[chain[i]]
        if not _jobs_capacity_compatible(prev_job, next_job):
            return False

        travel = tt.get((chain[i - 1], chain[i]), 999)
        min_arrival = current_arrival + travel + next_job.duration_minutes
        max_arrival = _entry_arrival_max(next_job)
        if min_arrival > max_arrival:
            return False

        effective = max(min_arrival, _entry_arrival_min(next_job))
        current_arrival = min(effective, max_arrival)

    return True


def _verify_exit_chain(
    chain: List[int],
    jobs: List[RouteJob],
    tt: Dict[Tuple[int, int], int]
) -> bool:
    """Verify an exit chain is feasible with -5/+10 min departure shifts."""
    if len(chain) <= 1:
        return True
    if not _chain_capacity_consistent(chain, jobs):
        return False

    departures = compute_effective_departures(chain, jobs, tt)
    for i, dep in enumerate(departures):
        if dep < _exit_departure_min(jobs[chain[i]]):
            return False
        if dep > _exit_departure_max(jobs[chain[i]]):
            return False
        if i > 0 and not _jobs_capacity_compatible(jobs[chain[i - 1]], jobs[chain[i]]):
            return False

    return True

def local_search_improve(
    buses: List[ChainedBus],
    block_jobs: Dict[int, List[RouteJob]],
    block_tt: Dict[int, Dict[Tuple[int, int], int]],
) -> List[ChainedBus]:
    """
    Iterative local search to reduce bus count.

    Strategy: try to empty buses by moving ALL their routes to other buses.
    For small buses (1-2 routes per block), try every possible insertion point.
    
    BUG FIX: Buses that receive routes are "frozen" and cannot be emptied in the
    same iteration. This prevents route accumulation where Bus A -> Bus B -> Bus C
    causes Bus C to accumulate all routes.
    """
    start_time = time_module.time()
    initial_count = len(buses)
    improvements = 0

    while time_module.time() - start_time < LOCAL_SEARCH_TIME_LIMIT:
        improved = False
        buses = [b for b in buses if not b.is_empty()]

        # Sort buses by total route count (smallest first = easiest to empty)
        bus_order = sorted(range(len(buses)), key=lambda i: buses[i].total_routes())
        
        # Track which buses have received routes (frozen - cannot be emptied)
        frozen_buses: Set[int] = set()

        for src_idx in bus_order:
            if src_idx in frozen_buses:
                continue
            
            # BUG FIX: Also skip buses that already have many routes
            # This prevents accumulation of routes in a single bus
            if buses[src_idx].total_routes() >= 12:
                continue
            if time_module.time() - start_time > LOCAL_SEARCH_TIME_LIMIT:
                break

            src = buses[src_idx]
            if src.is_empty():
                continue

            # Try to relocate ALL routes from this bus to others
            all_relocated = True
            relocations: List[Tuple[int, int, int, str]] = []  # (block, route_idx, target_bus_idx, position)
            planned_capacity_windows: Dict[int, Tuple[int, int]] = {
                idx: _get_bus_capacity_window(buses[idx], block_jobs) for idx in range(len(buses))
            }
            planned_chains: Dict[Tuple[int, int], List[int]] = {}

            for block in [1, 2, 3, 4]:
                chain = src.get_chain(block)
                if not chain:
                    continue

                jobs = block_jobs.get(block, [])
                tt = block_tt.get(block, {})
                is_entry = block in (1, 3)
                verify_fn = _verify_entry_chain if is_entry else _verify_exit_chain

                for route_idx in chain:
                    placed = False
                    route_window = _job_capacity_range(jobs[route_idx])
                    for tgt_idx in range(len(buses)):
                        if tgt_idx == src_idx:
                            continue
                        tgt = buses[tgt_idx]
                        tgt_window = planned_capacity_windows.get(tgt_idx, _get_bus_capacity_window(tgt, block_jobs))
                        
                        # BUG FIX: Don't add routes to buses that already have many routes
                        # This prevents accumulation of routes in a single bus
                        if tgt.total_routes() >= 12:
                            continue
                        if not _ranges_overlap(tgt_window[0], tgt_window[1], route_window[0], route_window[1]):
                            continue
                            
                        chain_key = (tgt_idx, block)
                        tgt_chain = list(planned_chains.get(chain_key, list(tgt.get_chain(block)) if tgt.has_block(block) else []))

                        # Try appending
                        new_chain = tgt_chain + [route_idx]
                        if verify_fn(new_chain, jobs, tt) and _chain_capacity_consistent(new_chain, jobs):
                            relocations.append((block, route_idx, tgt_idx, "append"))
                            planned_chains[chain_key] = new_chain
                            planned_capacity_windows[tgt_idx] = _merge_capacity_windows(tgt_window, route_window)
                            placed = True
                            break

                        # Try prepending
                        new_chain = [route_idx] + tgt_chain
                        if verify_fn(new_chain, jobs, tt) and _chain_capacity_consistent(new_chain, jobs):
                            relocations.append((block, route_idx, tgt_idx, "prepend"))
                            planned_chains[chain_key] = new_chain
                            planned_capacity_windows[tgt_idx] = _merge_capacity_windows(tgt_window, route_window)
                            placed = True
                            break

                        # Try inserting in the middle for chains with 2+ routes
                        if len(tgt_chain) >= 2:
                            for pos in range(1, len(tgt_chain)):
                                new_chain = tgt_chain[:pos] + [route_idx] + tgt_chain[pos:]
                                if verify_fn(new_chain, jobs, tt) and _chain_capacity_consistent(new_chain, jobs):
                                    relocations.append((block, route_idx, tgt_idx, f"insert_{pos}"))
                                    planned_chains[chain_key] = new_chain
                                    planned_capacity_windows[tgt_idx] = _merge_capacity_windows(tgt_window, route_window)
                                    placed = True
                                    break
                            if placed:
                                break

                    if not placed:
                        all_relocated = False
                        break

                if not all_relocated:
                    break

            if all_relocated and relocations:
                # Execute all relocations
                targets_used: Set[int] = set()
                for (block, route_idx, tgt_idx, position) in relocations:
                    tgt = buses[tgt_idx]
                    tgt_chain = list(tgt.get_chain(block)) if tgt.has_block(block) else []
                    if position == "append":
                        tgt.set_chain(block, tgt_chain + [route_idx])
                    elif position == "prepend":
                        tgt.set_chain(block, [route_idx] + tgt_chain)
                    elif position.startswith("insert_"):
                        pos = int(position.split("_")[1])
                        tgt.set_chain(block, tgt_chain[:pos] + [route_idx] + tgt_chain[pos:])
                    targets_used.add(tgt_idx)

                # Clear source bus
                for block in [1, 2, 3, 4]:
                    src.set_chain(block, [])

                # Freeze all target buses so they won't be emptied in this iteration
                # This prevents route accumulation (A -> B -> C problem)
                frozen_buses.update(targets_used)
                # Also freeze the source (now empty) to prevent any issues
                frozen_buses.add(src_idx)

                improved = True
                improvements += 1

        if not improved:
            break

    # Clean up
    buses = [b for b in buses if not b.is_empty()]

    elapsed = time_module.time() - start_time
    if improvements > 0:
        print(f"    Local search: removed {improvements} buses in {elapsed:.1f}s ({initial_count} -> {len(buses)})")
    else:
        print(f"    Local search: no improvements found ({elapsed:.1f}s)")

    return buses


# ============================================================
# PHASE 5: SCHEDULE CONSTRUCTION
# ============================================================

def compute_effective_arrivals(
    chain: List[int],
    jobs: List[RouteJob],
    travel_times: Dict[Tuple[int, int], int]
) -> List[int]:
    """Compute effective arrival times for an entry chain (window: +/-5 min)."""
    if not chain:
        return []

    n = len(chain)
    arrivals = [0] * n
    arrivals[0] = _entry_arrival_min(jobs[chain[0]])

    for i in range(1, n):
        prev_idx = chain[i - 1]
        curr_idx = chain[i]
        curr_job = jobs[curr_idx]
        tt = travel_times.get((prev_idx, curr_idx), 20)

        min_arrival = arrivals[i - 1] + tt + curr_job.duration_minutes
        max_arrival = _entry_arrival_max(curr_job)

        effective = max(min_arrival, _entry_arrival_min(curr_job))
        effective = min(effective, max_arrival)
        arrivals[i] = effective

    return arrivals


def compute_effective_departures(
    chain: List[int],
    jobs: List[RouteJob],
    travel_times: Dict[Tuple[int, int], int]
) -> List[int]:
    """Compute effective departure times for an exit chain (-5/+10 shift)."""
    if not chain:
        return []

    n = len(chain)
    departures = [0] * n
    departures[0] = _exit_departure_min(jobs[chain[0]])

    for i in range(1, n):
        prev_idx = chain[i - 1]
        curr_idx = chain[i]
        curr_job = jobs[curr_idx]
        tt = travel_times.get((prev_idx, curr_idx), 20)

        prev_end = departures[i - 1] + jobs[prev_idx].duration_minutes
        arrival_at_school = prev_end + tt

        effective = max(arrival_at_school, _exit_departure_min(curr_job))
        effective = min(effective, _exit_departure_max(curr_job))
        departures[i] = effective

    return departures

def _time_to_minutes(t) -> int:
    """Convert time to minutes since midnight."""
    if t is None:
        return 0
    return t.hour * 60 + t.minute


def _check_overlap_items(items: List[ScheduleItem]) -> List[ScheduleItem]:
    """
    Check for overlapping items and remove conflicting ones.
    Returns a list of non-overlapping items sorted by start time.
    """
    if not items:
        return items
    
    # Sort by start time
    sorted_items = sorted(items, key=lambda x: _time_to_minutes(x.start_time))
    
    # Remove overlapping items (keep first one, discard subsequent overlaps)
    valid_items: List[ScheduleItem] = []
    last_end_minutes = 0
    
    for item in sorted_items:
        start_mins = _time_to_minutes(item.start_time)
        end_mins = _time_to_minutes(item.end_time)
        
        # Add 5 min buffer between routes
        if start_mins >= last_end_minutes + 5:
            valid_items.append(item)
            last_end_minutes = end_mins
        else:
            # This item overlaps - log it but don't include
            logger.warning(f"Overlapping route removed: {item.route_id} ({item.start_time}-{item.end_time}) "
                          f"overlaps with previous ending at {last_end_minutes//60:02d}:{last_end_minutes%60:02d}")
    
    return valid_items


def _extract_item_start_location(item: ScheduleItem) -> Optional[Tuple[float, float]]:
    """Extract start coordinates from a schedule item."""
    if not item.stops:
        return None
    first = item.stops[0]
    if not coords_valid(first.lat, first.lon):
        return None
    return (first.lat, first.lon)


def _extract_item_end_location(item: ScheduleItem) -> Optional[Tuple[float, float]]:
    """Extract end coordinates from a schedule item."""
    if not item.stops:
        return None
    last = item.stops[-1]
    if not coords_valid(last.lat, last.lon):
        return None
    return (last.lat, last.lon)


def _required_connection_minutes(current: ScheduleItem, next_item: ScheduleItem) -> int:
    """
    Required minutes between consecutive routes:
    travel time + mandatory operational buffer.
    """
    end_loc = _extract_item_end_location(current)
    start_loc = _extract_item_start_location(next_item)

    if end_loc is None or start_loc is None:
        return 20 + MIN_CONNECTION_BUFFER_MINUTES

    return _connection_minutes_cached(end_loc, start_loc)


def _item_capacity_window(item: ScheduleItem) -> Tuple[int, int]:
    cap = int(getattr(item, "capacity_needed", 0) or 0)
    cap = max(1, cap)
    if cap <= SMALL_SERVICE_MAX_SEATS:
        return (1, SMALL_SERVICE_MAX_SEATS)

    low = int(getattr(item, "vehicle_capacity_min", 0) or 0)
    high = int(getattr(item, "vehicle_capacity_max", 0) or 0)
    if low > 0 and high > 0:
        return (min(low, high), max(low, high))
    if low > 0 and high <= 0:
        return (low, max(low, cap))
    if high > 0 and low <= 0:
        return (min(high, cap), high)

    margin = SMALL_BUS_CAPACITY_MAX_DIFF if cap <= SMALL_BUS_MAX_SEATS else CAPACITY_MAX_DIFF
    return (max(1, cap - margin), cap + margin)


def _split_items_by_connection_feasibility(items: List[ScheduleItem]) -> List[List[ScheduleItem]]:
    """
    Split one bus timeline into feasible segments, preserving all routes.

    Any transition without enough time (travel + buffer) starts a new segment.
    """
    if not items:
        return []

    sorted_items = sorted(items, key=lambda x: _time_to_minutes(x.start_time))
    segments: List[List[ScheduleItem]] = []
    current_segment: List[ScheduleItem] = [sorted_items[0]]
    current_window = _item_capacity_window(sorted_items[0])

    for item in sorted_items[1:]:
        prev = current_segment[-1]
        available = _time_to_minutes(item.start_time) - _time_to_minutes(prev.end_time)
        required = _required_connection_minutes(prev, item)
        next_window = _item_capacity_window(item)
        merged_window = _merge_capacity_windows(current_window, next_window)

        if available < required or merged_window == (0, 0):
            logger.info(
                "Split bus segment at %s -> %s (available=%s, required=%s, capacity_ok=%s)",
                prev.route_id,
                item.route_id,
                available,
                required,
                merged_window != (0, 0),
            )
            segments.append(current_segment)
            current_segment = [item]
            current_window = next_window
        else:
            current_segment.append(item)
            current_window = merged_window

    if current_segment:
        segments.append(current_segment)

    return segments


def build_full_schedule(
    buses: List[ChainedBus],
    block_jobs: Dict[int, List[RouteJob]],
    block_tt: Dict[int, Dict[Tuple[int, int], int]],
) -> List[BusSchedule]:
    """Build final BusSchedule objects with overlap validation."""
    schedules: List[BusSchedule] = []

    for bus_num, bus in enumerate(buses):
        items: List[ScheduleItem] = []
        bus_id = f"B{bus_num + 1:03d}"

        for block in [1, 2, 3, 4]:
            chain = bus.get_chain(block)
            if not chain:
                continue

            jobs = block_jobs.get(block, [])
            tt = block_tt.get(block, {})
            is_entry = block in (1, 3)

            if is_entry:
                arrivals = compute_effective_arrivals(chain, jobs, tt)
                for i, idx in enumerate(chain):
                    job = jobs[idx]
                    eff_arrival = arrivals[i]
                    start = eff_arrival - job.duration_minutes
                    shift = job.time_minutes - eff_arrival
                    deadhead = tt.get((chain[i - 1], idx), 0) if i > 0 else 0
                    items.append(_make_item(job, start, eff_arrival, shift, deadhead))
            else:
                departures = compute_effective_departures(chain, jobs, tt)
                for i, idx in enumerate(chain):
                    job = jobs[idx]
                    eff_departure = departures[i]
                    end = eff_departure + job.duration_minutes
                    shift = eff_departure - job.time_minutes  # Puede ser negativo (sale antes)
                    deadhead = tt.get((chain[i - 1], idx), 0) if i > 0 else 0
                    items.append(_make_item(job, eff_departure, end, shift, deadhead))

        # Split by real connection feasibility to avoid impossible transitions.
        if items:
            segments = _split_items_by_connection_feasibility(items)
            for idx, segment in enumerate(segments):
                if segment:
                    schedules.append(BusSchedule(bus_id=f"{bus_id}_{idx + 1}", items=segment))

    return schedules


def _reverse_exit_stops(stops: List[Stop]) -> List[Stop]:
    """
    Reverse stops for exit routes so they show school -> last drop-off.
    Recalculate time_from_start offsets for the reversed order.
    """
    if not stops or len(stops) < 2:
        return stops
    total_duration = max(s.time_from_start for s in stops)
    reversed_stops: List[Stop] = []
    for s in reversed(stops):
        new_stop = Stop(
            name=s.name,
            lat=s.lat,
            lon=s.lon,
            order=len(stops) - s.order + 1,
            time_from_start=total_duration - s.time_from_start,
            passengers=s.passengers,
            is_school=s.is_school
        )
        reversed_stops.append(new_stop)
    return reversed_stops


def _make_item(
    job: RouteJob, 
    start_mins: int, 
    end_mins: int, 
    shift: int, 
    deadhead: int
) -> ScheduleItem:
    """Create a ScheduleItem from a RouteJob."""
    # For exit routes, reverse stops so they go school -> drop-off stops
    stops = _reverse_exit_stops(job.route.stops) if job.route_type == "exit" else job.route.stops

    return ScheduleItem(
        route_id=job.route.id,
        start_time=from_minutes(start_mins),
        end_time=from_minutes(end_mins),
        type=job.route_type,
        capacity_needed=int(getattr(job.route, "capacity_needed", 0) or 0),
        vehicle_capacity_min=int(getattr(job.route, "vehicle_capacity_min", 0) or 0) or None,
        vehicle_capacity_max=int(getattr(job.route, "vehicle_capacity_max", 0) or 0) or None,
        vehicle_capacity_range=getattr(job.route, "vehicle_capacity_range", None),
        school_name=job.school_name,
        stops=stops,
        contract_id=job.route.contract_id,
        original_start_time=job.route.arrival_time if job.route_type == "entry" else job.route.departure_time,
        time_shift_minutes=int(shift),
        deadhead_minutes=int(deadhead),
        positioning_minutes=int(deadhead),
    )


# ============================================================
# MAIN ENTRY POINT
# ============================================================

ProgressCallback = Optional[callable]


def optimize_v6(
    routes: List[Route], 
    progress_callback: ProgressCallback = None,
    use_ml_assignment: bool = True,
) -> List[BusSchedule]:
    """
    Main optimization function for V6.
    
    Args:
        routes: List of Route objects to optimize
        progress_callback: Optional callback function(phase: str, progress: int, message: str) -> None
        use_ml_assignment: Enable ML pair scoring for route chaining
        
    Returns:
        List of BusSchedule objects representing the optimized fleet
    """
    
    global _LAST_OPTIMIZATION_DIAGNOSTICS
    _reset_runtime_metrics()
    try:
        reset_router_metrics()
    except Exception:
        pass

    def report_progress(phase: str, progress: int, message: str):
        """Helper to report progress via callback and/or print."""
        print(f"  [{phase}] {progress}% - {message}")
        if progress_callback:
            try:
                progress_callback(phase, progress, message)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
    
    print("\n" + "=" * 60)
    print("TUTTI OPTIMIZER V6 (ILP + Local Search)")
    print("=" * 60)
    print(f"ML assignment: {'enabled' if use_ml_assignment else 'disabled'}")

    # Phase 0: Prepare (0-10%)
    phase_start = time_module.perf_counter()
    report_progress("preprocessing", 5, "Preprocesando y validando rutas...")
    print("\n[Phase 0] Preprocessing & validation...")
    blocks = prepare_jobs(routes)
    for b in [1, 2, 3, 4]:
        block_type = {1: "Morning entries", 2: "Early exits", 3: "Late entries", 4: "Late exits"}[b]
        print(f"  Block {b} ({block_type}): {len(blocks[b])} routes")

    total_routes = sum(len(blocks[b]) for b in [1, 2, 3, 4])
    print(f"  Total routes to optimize: {total_routes}")
    _record_phase_time("preprocessing", phase_start)
    
    if total_routes == 0:
        router_metrics = {}
        try:
            router_metrics = get_router_metrics()
        except Exception:
            router_metrics = {}
        _LAST_OPTIMIZATION_DIAGNOSTICS = {
            "total_routes": 0,
            "pre_split_buses": 0,
            "best_buses": 0,
            "split_count": 0,
            "solver_status": "optimal",
            "lower_bound_buses": 0,
            "optimality_gap": 0.0,
            "avg_positioning_minutes": 0.0,
            "max_positioning_minutes": 0,
            "phase_time_sec": dict(_RUNTIME_METRICS.get("phase_time_sec", {})),
            "pairs_total": int(_RUNTIME_METRICS.get("pairs_total", 0)),
            "pairs_pruned": int(_RUNTIME_METRICS.get("pairs_pruned", 0)),
            "osrm_cache_hits": int(router_metrics.get("cache_hits", 0) or 0),
            "osrm_fallback_count": int(_RUNTIME_METRICS.get("osrm_fallback_count", 0)),
        }
        report_progress("completed", 100, "No hay rutas para optimizar")
        return []

    # Phase 1: Travel matrices (10-25%)
    phase_start = time_module.perf_counter()
    report_progress("travel_matrix", 15, "Calculando matrices de tiempos de viaje...")
    print("\n[Phase 1] Computing travel time matrices...")
    block_tt: Dict[int, Dict[Tuple[int, int], int]] = {}
    for b in [1, 2, 3, 4]:
        is_entry = b in (1, 3)
        block_tt[b] = precompute_block_travel_matrix(blocks[b], is_entry) if blocks[b] else {}
    save_cache()
    _record_phase_time("travel_matrix", phase_start)

    # Phase 2: Build chains per block (25-50%)
    phase_start = time_module.perf_counter()
    report_progress("building_chains", 35, "Construyendo cadenas óptimas por bloque...")
    print("\n[Phase 2] Building optimal chains per block (ILP)...")
    block_chains: Dict[int, List[List[int]]] = {}
    for b in [1, 2, 3, 4]:
        is_entry = b in (1, 3)
        block_name = {1: "Morning entries", 2: "Early exits", 3: "Late entries", 4: "Late exits"}[b]
        block_chains[b] = build_block_chains(
            blocks[b],
            block_tt[b],
            is_entry,
            block_name,
            use_ml_assignment=use_ml_assignment,
        )

    for b, name in [(1, "Morning entries"), (2, "Early exits"), (3, "Late entries"), (4, "Late exits")]:
        chains = block_chains[b]
        if chains:
            sizes = [len(c) for c in chains]
            print(f"  Block {b} ({name}): {len(chains)} chains, sizes: {min(sizes)}-{max(sizes)}, avg={sum(sizes)/len(sizes):.1f}")
    _record_phase_time("building_chains", phase_start)

    # Phase 3: Cross-block merging (50-70%)
    phase_start = time_module.perf_counter()
    report_progress("matching_blocks", 60, "Emparejando bloques temporales...")
    print("\n[Phase 3] Cross-block merging (ILP matching)...")
    bus_list = merge_all_blocks(block_chains, blocks)
    print(f"  Total buses after merge: {len(bus_list)}")

    # Diagnostic
    block_combos: Dict[Tuple[int, ...], int] = {}
    for bus in bus_list:
        combo = tuple(sorted(b for b in [1, 2, 3, 4] if bus.has_block(b)))
        block_combos[combo] = block_combos.get(combo, 0) + 1
    for combo, count in sorted(block_combos.items()):
        labels = {1: "B1", 2: "B2", 3: "B3", 4: "B4"}
        combo_str = "+".join(labels[b] for b in combo)
        print(f"    {combo_str}: {count} buses")
    _record_phase_time("matching_blocks", phase_start)

    # Phase 4: Local search (70-85%)
    phase_start = time_module.perf_counter()
    report_progress("local_search", 80, "Optimizando con búsqueda local...")
    print("\n[Phase 4] Local search improvement...")
    baseline_buses = deepcopy(bus_list)
    candidate_buses = local_search_improve(deepcopy(bus_list), blocks, block_tt)

    baseline_schedules = build_full_schedule(baseline_buses, blocks, block_tt)
    candidate_schedules = build_full_schedule(candidate_buses, blocks, block_tt)

    baseline_split = max(0, len(baseline_schedules) - len(baseline_buses))
    candidate_split = max(0, len(candidate_schedules) - len(candidate_buses))

    use_candidate = False
    if candidate_split < baseline_split:
        use_candidate = True
    elif candidate_split == baseline_split and len(candidate_schedules) < len(baseline_schedules):
        use_candidate = True

    if use_candidate:
        bus_list = candidate_buses
        prebuilt_schedules = candidate_schedules
        print(
            f"    Local search accepted: split {baseline_split}->{candidate_split}, "
            f"buses {len(baseline_schedules)}->{len(candidate_schedules)}"
        )
    else:
        bus_list = baseline_buses
        prebuilt_schedules = baseline_schedules
        print(
            f"    Local search reverted: split {baseline_split}->{candidate_split}, "
            f"buses {len(baseline_schedules)}->{len(candidate_schedules)}"
        )
    _record_phase_time("local_search", phase_start)

    # Phase 5: Build schedules (85-95%)
    phase_start = time_module.perf_counter()
    report_progress("finalizing", 90, "Construyendo horarios finales...")
    print("\n[Phase 5] Building final schedules...")
    pre_split_buses = len(bus_list)
    schedules = prebuilt_schedules
    split_count = max(0, len(schedules) - pre_split_buses)

    # Remove empty and renumber
    schedules = [s for s in schedules if s.items]
    for i, s in enumerate(schedules):
        s.bus_id = f"B{i + 1:03d}"
    _record_phase_time("finalizing", phase_start)

    # Statistics
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    lower_bound_buses = max(0, pre_split_buses)
    best_buses = len(schedules)
    if lower_bound_buses <= 0:
        optimality_gap = 0.0
    else:
        optimality_gap = round(max(0, best_buses - lower_bound_buses) / float(lower_bound_buses), 4)

    router_metrics = {}
    try:
        router_metrics = get_router_metrics()
    except Exception:
        router_metrics = {}

    _LAST_OPTIMIZATION_DIAGNOSTICS = {
        "total_routes": total_routes,
        "pre_split_buses": pre_split_buses,
        "best_buses": best_buses,
        "split_count": split_count,
        "solver_status": "optimal" if split_count == 0 else "feasible",
        "lower_bound_buses": lower_bound_buses,
        "optimality_gap": optimality_gap,
        "avg_positioning_minutes": 0.0,
        "max_positioning_minutes": 0,
        "phase_time_sec": dict(_RUNTIME_METRICS.get("phase_time_sec", {})),
        "pairs_total": int(_RUNTIME_METRICS.get("pairs_total", 0)),
        "pairs_pruned": int(_RUNTIME_METRICS.get("pairs_pruned", 0)),
        "osrm_cache_hits": int(router_metrics.get("cache_hits", 0) or 0),
        "osrm_fallback_count": int(_RUNTIME_METRICS.get("osrm_fallback_count", 0)),
    }
    total_assigned = sum(len(s.items) for s in schedules)
    entry_count = sum(1 for s in schedules for item in s.items if item.type == "entry")
    exit_count = sum(1 for s in schedules for item in s.items if item.type == "exit")
    routes_per_bus = [len(s.items) for s in schedules]

    print(f"  Total buses: {len(schedules)}")
    print(f"  Total routes assigned: {total_assigned}")
    print(f"  Entries: {entry_count}, Exits: {exit_count}")
    if routes_per_bus:
        print(f"  Routes/bus: min={min(routes_per_bus)}, max={max(routes_per_bus)}, avg={sum(routes_per_bus)/len(routes_per_bus):.1f}")

    shifts = [item.time_shift_minutes for s in schedules for item in s.items if item.time_shift_minutes > 0]
    if shifts:
        print(f"  Shifts: min={min(shifts)}m, max={max(shifts)}m, avg={sum(shifts)/len(shifts):.1f}m")

    deadheads = [item.deadhead_minutes for s in schedules for item in s.items if item.deadhead_minutes > 0]
    if deadheads:
        print(f"  Deadheads: min={min(deadheads)}m, max={max(deadheads)}m, avg={sum(deadheads)/len(deadheads):.1f}m")
        _LAST_OPTIMIZATION_DIAGNOSTICS["avg_positioning_minutes"] = round(sum(deadheads) / len(deadheads), 2)
        _LAST_OPTIMIZATION_DIAGNOSTICS["max_positioning_minutes"] = int(max(deadheads))

    print(f"  Phase times (sec): {_LAST_OPTIMIZATION_DIAGNOSTICS['phase_time_sec']}")
    print(
        "  Pair pruning: "
        f"{_LAST_OPTIMIZATION_DIAGNOSTICS['pairs_pruned']}/{_LAST_OPTIMIZATION_DIAGNOSTICS['pairs_total']}"
    )
    print(
        "  OSRM metrics: "
        f"cache_hits={_LAST_OPTIMIZATION_DIAGNOSTICS['osrm_cache_hits']}, "
        f"fallbacks={_LAST_OPTIMIZATION_DIAGNOSTICS['osrm_fallback_count']}"
    )

    for s in schedules:
        entries_in = [i for i in s.items if i.type == "entry"]
        exits_in = [i for i in s.items if i.type == "exit"]
        schools = set(i.school_name for i in s.items)
        print(f"  {s.bus_id}: {len(entries_in)}E + {len(exits_in)}X = {len(s.items)} total, {len(schools)} schools")

    print("=" * 60)
    
    # Final progress update
    report_progress("completed", 100, f"Optimización completada: {len(schedules)} buses")
    
    return schedules


def optimize_routes_v6(routes: List[Route], use_ml_assignment: bool = True) -> List[BusSchedule]:
    """Alias for optimize_v6."""
    return optimize_v6(routes, use_ml_assignment=use_ml_assignment)


__all__ = ['optimize_v6', 'optimize_routes_v6', 'get_last_optimization_diagnostics']




