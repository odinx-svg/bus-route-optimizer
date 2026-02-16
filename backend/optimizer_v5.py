"""
Optimizer V5 - Tutti Route Optimizer
=====================================

GOAL: Minimize buses by chaining as many routes as possible per bus.

REAL SCHEDULE HAS 4 TIME BLOCKS:
1. Morning entries (08:00-09:30): Pickup kids -> deliver to school. CAN shift earlier.
2. Early afternoon exits (14:00-16:10): School ends -> deliver kids home. FIXED time.
3. Late afternoon entries (16:20-16:40): Pickup kids -> deliver to school (afternoon classes). CAN shift earlier.
4. Late afternoon exits (18:20-18:40): School ends -> deliver kids home. FIXED time.

A single bus can potentially do: block1 -> block2 -> block3 -> block4

For entries (blocks 1 & 3): We can shift arrival earlier to chain more.
For exits (blocks 2 & 4): Departure time is FIXED.

Uses OSRM for real driving times via router_service.py.
"""

import logging
import math
from typing import List, Dict, Tuple, Optional, Set, Any
from datetime import time
from dataclasses import dataclass

from models import Route, BusSchedule, ScheduleItem, Stop
from router_service import get_real_travel_time, get_route_duration, get_travel_time_matrix, save_cache

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

MAX_EARLY_ARRIVAL_MINUTES: int = 0    # Entradas ya vienen ajustadas en Excel
MAX_EXIT_SHIFT_MINUTES: int = 5       # ±5 min flexibilidad en salidas
DEADHEAD_BUFFER_MINUTES: int = 3     # Buffer on top of travel time
FALLBACK_SPEED_KMH: int = 50        # For haversine fallback
EARTH_RADIUS_KM: float = 6371.0
# Block boundaries (minutes since midnight)
MORNING_ENTRY_MAX: int = 11 * 60     # Morning entries arrive before 11:00
EARLY_EXIT_MAX: int = 16 * 60 + 15   # Early exits depart before 16:15
LATE_ENTRY_MAX: int = 18 * 60        # Late entries arrive before 18:00

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
    """Calculate distance using haversine formula."""
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


def get_travel_time(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """Get travel time using OSRM or haversine fallback."""
    if lat1 == 0 or lon1 == 0 or lat2 == 0 or lon2 == 0:
        return 20
    osrm_time = get_real_travel_time(lat1, lon1, lat2, lon2)
    if osrm_time is not None:
        return osrm_time + DEADHEAD_BUFFER_MINUTES
    return haversine_travel_minutes(lat1, lon1, lat2, lon2)


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class RouteJob:
    """Represents a route job for optimization."""
    route: Route
    route_type: str           # "entry" or "exit"
    block: int                # 1=morning entry, 2=early exit, 3=late entry, 4=late exit
    school_name: str
    school_loc: Tuple[float, float]
    first_stop: Tuple[float, float]
    last_stop: Tuple[float, float]
    duration_minutes: int
    time_minutes: int         # arrival_minutes for entries, departure_minutes for exits
    original_index: int = 0


# ============================================================
# PRECOMPUTATION
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
            if mins <= MORNING_ENTRY_MAX:
                return 1  # Morning entry
            else:
                return 3  # Late afternoon entry
        # Entry without arrival_time: try departure_time as fallback
        if route.departure_time:
            mins = to_minutes(route.departure_time)
            # An entry route with departure_time: departure is when it leaves first stop
            # Estimate arrival = departure + ~30 min duration
            estimated_arrival = mins + 30
            if estimated_arrival <= MORNING_ENTRY_MAX:
                return 1
            else:
                return 3
    elif route.type == "exit":
        if route.departure_time:
            mins = to_minutes(route.departure_time)
            if mins <= EARLY_EXIT_MAX:
                return 2  # Early afternoon exit
            else:
                return 4  # Late afternoon exit
        # Exit without departure_time: try arrival_time as fallback
        if route.arrival_time:
            mins = to_minutes(route.arrival_time)
            # An exit route with arrival_time: arrival is when bus finishes
            # Estimate departure = arrival - ~30 min duration
            estimated_departure = mins - 30
            if estimated_departure <= EARLY_EXIT_MAX:
                return 2
            else:
                return 4
    return 0  # Unknown


def prepare_jobs(routes: List[Route]) -> Dict[int, List[RouteJob]]:
    """Prepare route jobs organized by block."""
    blocks: Dict[int, List[RouteJob]] = {1: [], 2: [], 3: [], 4: []}
    dropped: List[Route] = []

    for i, route in enumerate(routes):
        block = classify_block(route)
        if block == 0:
            dropped.append(route)
            continue

        duration = compute_route_duration(route)

        if route.stops and len(route.stops) > 0:
            first_stop = (route.stops[0].lat, route.stops[0].lon)
            last_stop = (route.stops[-1].lat, route.stops[-1].lon)
        else:
            first_stop = (0.0, 0.0)
            last_stop = (0.0, 0.0)

        # Determine time_minutes with fallbacks
        if route.type == "entry":
            if route.arrival_time:
                time_mins = to_minutes(route.arrival_time)
            elif route.departure_time:
                time_mins = to_minutes(route.departure_time) + duration
            else:
                time_mins = 9 * 60  # Default 09:00 for entries
            school_loc = last_stop   # Entry: last stop is school
        else:
            if route.departure_time:
                time_mins = to_minutes(route.departure_time)
            elif route.arrival_time:
                time_mins = to_minutes(route.arrival_time) - duration
            else:
                time_mins = 14 * 60  # Default 14:00 for exits
            school_loc = first_stop  # Exit: first stop is school

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
            original_index=i
        )
        blocks[block].append(job)

    if dropped:
        print(f"  WARNING: {len(dropped)} routes dropped (no time info):")
        for r in dropped:
            print(f"    - {r.id} ({r.type}): arrival={r.arrival_time}, departure={r.departure_time}")

    return blocks


def precompute_travel_matrix_for_block(
    jobs: List[RouteJob], 
    is_entry: bool
) -> Dict[Tuple[int, int], int]:
    """
    Precompute travel times within a block.
    For entries: travel from school_loc[i] to first_stop[j] (school->next pickup)
    For exits: travel from last_stop[i] to school_loc[j] (last dropoff->next school)
    """
    n = len(jobs)
    if n == 0:
        return {}

    if is_entry:
        sources = [job.school_loc for job in jobs]
        destinations = [job.first_stop for job in jobs]
    else:
        sources = [job.last_stop for job in jobs]
        destinations = [job.school_loc for job in jobs]

    matrix_result = get_travel_time_matrix(sources, destinations)

    travel_times: Dict[Tuple[int, int], int] = {}
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            t = matrix_result[i][j] if matrix_result and matrix_result[i][j] is not None else None
            if t is not None:
                travel_times[(i, j)] = t + DEADHEAD_BUFFER_MINUTES
            else:
                travel_times[(i, j)] = haversine_travel_minutes(
                    sources[i][0], sources[i][1],
                    destinations[j][0], destinations[j][1]
                )
    return travel_times


# ============================================================
# CHAIN BUILDING - ENTRIES (can shift earlier)
# ============================================================

def build_entry_chains(
    jobs: List[RouteJob], 
    travel_times: Dict[Tuple[int, int], int]
) -> List[List[int]]:
    """
    Build chains for entry routes (morning or afternoon entries).
    Can shift arrival earlier by up to MAX_EARLY_ARRIVAL_MINUTES.
    """
    n = len(jobs)
    if n == 0:
        return []

    best_chains: Optional[List[List[int]]] = None
    best_count = float('inf')

    # Try 3 seeding strategies
    strategies: List[List[int]] = [
        sorted(range(n), key=lambda i: jobs[i].time_minutes),
        sorted(range(n), key=lambda i: -jobs[i].time_minutes),
    ]

    # Connectivity-based strategy
    connectivity: Dict[int, int] = {}
    for i in range(n):
        count = 0
        for j in range(n):
            if i == j:
                continue
            tt = travel_times.get((i, j), 999)
            can_reach = jobs[i].time_minutes + tt <= jobs[j].time_minutes - jobs[j].duration_minutes + MAX_EARLY_ARRIVAL_MINUTES
            if can_reach:
                count += 1
        connectivity[i] = count
    strategies.append(sorted(range(n), key=lambda i: -connectivity.get(i, 0)))

    for seed_order in strategies:
        chains = _greedy_chain_entries(jobs, travel_times, seed_order)
        if len(chains) < best_count:
            best_count = len(chains)
            best_chains = chains

    return best_chains if best_chains is not None else []


def _greedy_chain_entries(
    jobs: List[RouteJob], 
    travel_times: Dict[Tuple[int, int], int], 
    seed_order: List[int]
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

        seed_job = jobs[seed_idx]
        # First route: shift as early as possible
        current_arrival = seed_job.time_minutes - MAX_EARLY_ARRIVAL_MINUTES
        route_start = current_arrival - seed_job.duration_minutes
        if route_start < 6 * 60:
            current_arrival = 6 * 60 + seed_job.duration_minutes
        current_arrival = min(current_arrival, seed_job.time_minutes)

        while True:
            best_next: Optional[int] = None
            best_score = float('inf')
            best_arrival = 0

            for j in range(n):
                if j in assigned:
                    continue

                next_job = jobs[j]
                tt = travel_times.get((chain[-1], j), 999)

                # Bus arrives at first stop of route j at:
                arrival_at_first_stop = current_arrival + tt

                # Route j needs to start at: effective_arrival_j - duration_j
                # Effective arrival can be between [time - MAX_EARLY, time]
                min_effective = arrival_at_first_stop + next_job.duration_minutes
                max_effective = next_job.time_minutes

                if min_effective > max_effective:
                    continue  # Can't reach

                effective = max(min_effective, next_job.time_minutes - MAX_EARLY_ARRIVAL_MINUTES)
                effective = min(effective, max_effective)

                deadhead = tt
                wasted = max(0, (effective - next_job.duration_minutes) - arrival_at_first_stop)
                score = deadhead * 2 + wasted

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


# ============================================================
# CHAIN BUILDING - EXITS (fixed departure)
# ============================================================

def build_exit_chains(
    jobs: List[RouteJob], 
    travel_times: Dict[Tuple[int, int], int]
) -> List[List[int]]:
    """Build chains for exit routes. Departure times are FIXED."""
    n = len(jobs)
    if n == 0:
        return []

    best_chains: Optional[List[List[int]]] = None
    best_count = float('inf')

    # Strategy 1: seed by earliest departure
    strategies: List[List[int]] = [
        sorted(range(n), key=lambda i: jobs[i].time_minutes),
    ]

    # Strategy 2: seed by latest departure (reverse)
    strategies.append(sorted(range(n), key=lambda i: -jobs[i].time_minutes))

    # Strategy 3: seed by most chainable (connectivity-based)
    connectivity: Dict[int, int] = {}
    for i in range(n):
        count = 0
        for j in range(n):
            if i == j:
                continue
            tt = travel_times.get((i, j), 999)
            earliest_end_i = (jobs[i].time_minutes - MAX_EXIT_SHIFT_MINUTES) + jobs[i].duration_minutes
            latest_start_j = jobs[j].time_minutes + MAX_EXIT_SHIFT_MINUTES
            if earliest_end_i + tt <= latest_start_j:
                count += 1
        connectivity[i] = count
    strategies.append(sorted(range(n), key=lambda i: -connectivity.get(i, 0)))

    # Strategy 4: seed by UNIQUE departure times first (avoid creating many single-route chains)
    # Routes at unique times are harder to chain later, so prioritize them as seeds
    from collections import Counter
    time_counts = Counter(jobs[i].time_minutes for i in range(n))
    strategies.append(sorted(range(n), key=lambda i: (time_counts[jobs[i].time_minutes], jobs[i].time_minutes)))

    for seed_order in strategies:
        chains = _greedy_chain_exits(jobs, travel_times, seed_order)
        if len(chains) < best_count:
            best_count = len(chains)
            best_chains = chains

    return best_chains if best_chains is not None else []


def _greedy_chain_exits(
    jobs: List[RouteJob], 
    travel_times: Dict[Tuple[int, int], int], 
    seed_order: List[int]
) -> List[List[int]]:
    """Greedy chain builder for exit routes with ±5min shift flexibility."""
    n = len(jobs)
    assigned: Set[int] = set()
    chains: List[List[int]] = []

    for seed_idx in seed_order:
        if seed_idx in assigned:
            continue

        chain = [seed_idx]
        assigned.add(seed_idx)

        seed_job = jobs[seed_idx]
        # Seed: puede salir hasta 5 min antes
        current_end = (seed_job.time_minutes - MAX_EXIT_SHIFT_MINUTES) + seed_job.duration_minutes

        while True:
            best_next: Optional[int] = None
            best_score = float('inf')

            for j in range(n):
                if j in assigned:
                    continue

                next_job = jobs[j]
                tt = travel_times.get((chain[-1], j), 999)

                arrival_at_school = current_end + tt

                # Check: la segunda ruta puede salir hasta 5 min después
                if arrival_at_school > next_job.time_minutes + MAX_EXIT_SHIFT_MINUTES:
                    continue  # Too late

                # Espera efectiva considerando el shift permitido
                effective_departure = max(next_job.time_minutes - MAX_EXIT_SHIFT_MINUTES, arrival_at_school)
                wait = effective_departure - arrival_at_school
                score = tt * 2 + wait

                if score < best_score:
                    best_score = score
                    best_next = j

            if best_next is not None:
                chain.append(best_next)
                assigned.add(best_next)
                next_job = jobs[best_next]
                # Calcular el effective departure para la siguiente ruta
                tt = travel_times.get((chain[-2], best_next), 999)
                arrival = current_end + tt
                effective_departure = max(next_job.time_minutes - MAX_EXIT_SHIFT_MINUTES, arrival)
                effective_departure = min(effective_departure, next_job.time_minutes + MAX_EXIT_SHIFT_MINUTES)
                current_end = effective_departure + next_job.duration_minutes
            else:
                break

        chains.append(chain)

    return chains


# ============================================================
# CROSS-BLOCK MERGING
# ============================================================

@dataclass
class BusChain:
    """Represents a full day schedule for one bus."""
    bus_id: str = ""
    # Each block holds a list of job indices (within that block's job list)
    block1_chain: Optional[List[int]] = None  # morning entries
    block2_chain: Optional[List[int]] = None  # early exits
    block3_chain: Optional[List[int]] = None  # late entries
    block4_chain: Optional[List[int]] = None  # late exits


def merge_blocks(
    block1_chains: List[List[int]], b1_jobs: List[RouteJob],
    block2_chains: List[List[int]], b2_jobs: List[RouteJob],
    block3_chains: List[List[int]], b3_jobs: List[RouteJob],
    block4_chains: List[List[int]], b4_jobs: List[RouteJob],
) -> List[BusChain]:
    """
    Merge chains across 4 blocks to minimize total buses.

    Strategy: greedy sequential merging.
    1. Start with block1 chains (morning entries)
    2. Try to attach a block2 chain (early exit) to each
    3. Try to attach a block3 chain (late entry) to each
    4. Try to attach a block4 chain (late exit) to each
    """

    buses: List[BusChain] = []

    # Initialize with block1 chains
    for chain in block1_chains:
        buses.append(BusChain(block1_chain=chain))

    # Merge block2 onto buses
    _merge_block_onto_buses(buses, block2_chains, b2_jobs,
                            prev_block_key="block1_chain", prev_jobs=b1_jobs,
                            new_block_key="block2_chain", is_prev_entry=True)

    # Merge block3 onto buses
    _merge_block_onto_buses(buses, block3_chains, b3_jobs,
                            prev_block_key="block2_chain", prev_jobs=b2_jobs,
                            new_block_key="block3_chain", is_prev_entry=False)

    # Merge block4 onto buses
    _merge_block_onto_buses(buses, block4_chains, b4_jobs,
                            prev_block_key="block3_chain", prev_jobs=b3_jobs,
                            new_block_key="block4_chain", is_prev_entry=True)

    return buses


def _get_bus_end_info(
    bus: BusChain, 
    block_key: str, 
    jobs: List[RouteJob]
) -> Optional[Tuple[int, Tuple[float, float]]]:
    """Get end time and location of a bus's last active block."""
    chain: Optional[List[int]] = getattr(bus, block_key)
    if not chain or not jobs:
        return None
    last_job = jobs[chain[-1]]
    if last_job.route_type == "entry":
        end_time = last_job.time_minutes  # Arrival at school
        end_loc = last_job.school_loc
    else:
        end_time = last_job.time_minutes + last_job.duration_minutes
        end_loc = last_job.last_stop
    return (end_time, end_loc)


def _merge_block_onto_buses(
    buses: List[BusChain],
    new_chains: List[List[int]],
    new_jobs: List[RouteJob],
    prev_block_key: str,
    prev_jobs: List[RouteJob],
    new_block_key: str,
    is_prev_entry: bool
) -> None:
    """Try to attach new block chains to existing buses."""
    if not new_chains:
        return

    chain_used: Set[int] = set()

    # Sort buses by end time of previous block (earliest end -> most time available)
    bus_order = list(range(len(buses)))

    for bus_idx in bus_order:
        bus = buses[bus_idx]

        # Get end info from the LATEST active block on this bus
        end_info: Optional[Tuple[int, Tuple[float, float]]] = None
        # Check blocks in reverse order to find latest
        for bk, bj in [(prev_block_key, prev_jobs)]:
            info = _get_bus_end_info(bus, bk, bj)
            if info:
                end_info = info
                break

        if end_info is None:
            # No previous block, try earlier blocks
            # Check block1 if we're looking at block2, etc.
            if prev_block_key == "block2_chain" and bus.block1_chain and prev_jobs:
                # Actually prev_jobs here is b2_jobs but we need b1_jobs...
                # This is handled differently - skip for now
                pass
            continue

        end_time, end_loc = end_info

        best_chain_idx: Optional[int] = None
        best_gap = float('inf')

        for c_idx, chain in enumerate(new_chains):
            if c_idx in chain_used:
                continue

            first_job = new_jobs[chain[0]]

            # Compute travel time
            if first_job.route_type == "entry":
                dest_loc = first_job.first_stop
                chain_start = first_job.time_minutes - first_job.duration_minutes - MAX_EARLY_ARRIVAL_MINUTES
            else:
                dest_loc = first_job.school_loc
                chain_start = first_job.time_minutes

            tt = get_travel_time(end_loc[0], end_loc[1], dest_loc[0], dest_loc[1])
            arrival = end_time + tt

            if arrival <= chain_start + 5:  # 5 min flex
                gap = chain_start - arrival
                if gap < best_gap:
                    best_gap = gap
                    best_chain_idx = c_idx

        if best_chain_idx is not None:
            setattr(bus, new_block_key, new_chains[best_chain_idx])
            chain_used.add(best_chain_idx)

    # Add unmerged chains as new buses
    for c_idx, chain in enumerate(new_chains):
        if c_idx not in chain_used:
            new_bus = BusChain()
            setattr(new_bus, new_block_key, chain)
            buses.append(new_bus)


# ============================================================
# BETTER CROSS-BLOCK MERGING (handles all block transitions)
# ============================================================

def merge_blocks_v2(
    block1_chains: List[List[int]], b1_jobs: List[RouteJob],
    block2_chains: List[List[int]], b2_jobs: List[RouteJob],
    block3_chains: List[List[int]], b3_jobs: List[RouteJob],
    block4_chains: List[List[int]], b4_jobs: List[RouteJob],
) -> List[BusChain]:
    """
    Smart merging: process block by block, sort buses by end time for optimal matching.
    After initial merge, run consolidation to absorb exit-only buses into morning buses.
    """
    buses: List[BusChain] = []

    # Start with block1 chains
    for chain in block1_chains:
        buses.append(BusChain(block1_chain=chain))

    # ── Attach block2 chains ──
    # Sort buses by end time (earliest first = most time to reach next)
    b2_used: Set[int] = set()
    bus_ends: List[Tuple[int, int, Tuple[float, float]]] = []
    for bi, bus in enumerate(buses):
        if bus.block1_chain:
            last_j = b1_jobs[bus.block1_chain[-1]]
            bus_ends.append((bi, last_j.time_minutes, last_j.school_loc))
    bus_ends.sort(key=lambda x: x[1])  # earliest end first

    for bi, end_time, end_loc in bus_ends:
        best_c, best_gap = _find_best_exit_chain(end_time, end_loc, block2_chains, b2_jobs, b2_used)
        if best_c is not None:
            buses[bi].block2_chain = block2_chains[best_c]
            b2_used.add(best_c)

    # Remaining block2 -> new buses
    for c_idx, chain in enumerate(block2_chains):
        if c_idx not in b2_used:
            buses.append(BusChain(block2_chain=chain))

    # ── Attach block3 chains ──
    b3_used: Set[int] = set()
    bus_ends = []
    for bi, bus in enumerate(buses):
        latest = _get_latest_end(bus, b1_jobs, b2_jobs, b3_jobs, b4_jobs)
        if latest[0] is not None and latest[1] is not None:
            bus_ends.append((bi, latest[0], latest[1]))
    bus_ends.sort(key=lambda x: x[1])

    for bi, end_time, end_loc in bus_ends:
        best_c, _ = _find_best_entry_chain(end_time, end_loc, block3_chains, b3_jobs, b3_used)
        if best_c is not None:
            buses[bi].block3_chain = block3_chains[best_c]
            b3_used.add(best_c)

    for c_idx, chain in enumerate(block3_chains):
        if c_idx not in b3_used:
            buses.append(BusChain(block3_chain=chain))

    # ── Attach block4 chains ──
    b4_used: Set[int] = set()
    bus_ends = []
    for bi, bus in enumerate(buses):
        latest = _get_latest_end(bus, b1_jobs, b2_jobs, b3_jobs, b4_jobs)
        if latest[0] is not None and latest[1] is not None:
            bus_ends.append((bi, latest[0], latest[1]))
    bus_ends.sort(key=lambda x: x[1])

    for bi, end_time, end_loc in bus_ends:
        best_c, _ = _find_best_exit_chain(end_time, end_loc, block4_chains, b4_jobs, b4_used)
        if best_c is not None:
            buses[bi].block4_chain = block4_chains[best_c]
            b4_used.add(best_c)

    for c_idx, chain in enumerate(block4_chains):
        if c_idx not in b4_used:
            buses.append(BusChain(block4_chain=chain))

    # ── CONSOLIDATION PASS ──
    # Try to merge buses that only have exits into buses that only have entries
    # (or into buses that have entries + exits but still have room for more blocks)
    buses = _consolidate_buses(buses, b1_jobs, b2_jobs, b3_jobs, b4_jobs)

    return buses


def _consolidate_buses(
    buses: List[BusChain],
    b1_jobs: List[RouteJob], b2_jobs: List[RouteJob],
    b3_jobs: List[RouteJob], b4_jobs: List[RouteJob],
) -> List[BusChain]:
    """
    Consolidation pass: merge exit-only or partial buses into buses with available capacity.

    KEY INSIGHT: A bus with block1+block2 already can still absorb MORE block2 exits
    if its last block2 exit ends before the source's first block2 exit starts.
    We do this by APPENDING to the existing block2_chain.
    """
    MAX_CONSOLIDATION_GAP = 300  # Max 5 hours gap (morning to afternoon is normal)

    merged_away: Set[int] = set()

    for pass_num in range(5):  # Multiple passes
        progress = False
        for src_idx in range(len(buses)):
            if src_idx in merged_away:
                continue
            src = buses[src_idx]

            # ── Exit-only bus (block2 only) → merge into any bus that can reach it ──
            if src.block2_chain and not src.block1_chain and not src.block3_chain and not src.block4_chain:
                first_exit = b2_jobs[src.block2_chain[0]]
                exit_start = first_exit.time_minutes

                best_target: Optional[int] = None
                best_gap = float('inf')

                for tgt_idx in range(len(buses)):
                    if tgt_idx in merged_away or tgt_idx == src_idx:
                        continue
                    tgt = buses[tgt_idx]

                    # Target can absorb if:
                    # 1. It has NO block2 chain, OR
                    # 2. Its block2 chain ENDS before src's block2 chain STARTS (append)
                    if tgt.block2_chain:
                        # Check if target's block2 ends before source's block2 starts
                        last_tgt_exit = b2_jobs[tgt.block2_chain[-1]]
                        tgt_b2_end = last_tgt_exit.time_minutes + last_tgt_exit.duration_minutes
                        tt = get_travel_time(last_tgt_exit.last_stop[0], last_tgt_exit.last_stop[1],
                                             first_exit.school_loc[0], first_exit.school_loc[1])
                        if tgt_b2_end + tt <= exit_start:
                            gap = exit_start - (tgt_b2_end + tt)
                            if gap < best_gap:
                                best_gap = gap
                                best_target = tgt_idx
                    else:
                        # No block2 yet - check from latest end
                        tgt_end = _get_latest_end(tgt, b1_jobs, b2_jobs, b3_jobs, b4_jobs)
                        if tgt_end[0] is None or tgt_end[1] is None:
                            continue

                        tt = get_travel_time(tgt_end[1][0], tgt_end[1][1],
                                             first_exit.school_loc[0], first_exit.school_loc[1])
                        arrival = tgt_end[0] + tt
                        if arrival <= exit_start and (exit_start - tgt_end[0]) < MAX_CONSOLIDATION_GAP:
                            gap = exit_start - arrival
                            if gap < best_gap:
                                best_gap = gap
                                best_target = tgt_idx

                if best_target is not None:
                    tgt = buses[best_target]
                    if tgt.block2_chain:
                        # APPEND to existing block2 chain
                        tgt.block2_chain = tgt.block2_chain + src.block2_chain
                    else:
                        tgt.block2_chain = src.block2_chain
                    src.block2_chain = None
                    merged_away.add(src_idx)
                    progress = True
                    continue

            # ── Block4-only bus → merge into any bus with earlier blocks ──
            if src.block4_chain and not src.block1_chain and not src.block2_chain and not src.block3_chain:
                first_exit = b4_jobs[src.block4_chain[0]]
                exit_start = first_exit.time_minutes

                best_target = None
                best_gap = float('inf')

                for tgt_idx in range(len(buses)):
                    if tgt_idx in merged_away or tgt_idx == src_idx:
                        continue
                    tgt = buses[tgt_idx]

                    if tgt.block4_chain:
                        # Can append if target block4 ends before src block4 starts
                        last_tgt_exit = b4_jobs[tgt.block4_chain[-1]]
                        tgt_b4_end = last_tgt_exit.time_minutes + last_tgt_exit.duration_minutes
                        tt = get_travel_time(last_tgt_exit.last_stop[0], last_tgt_exit.last_stop[1],
                                             first_exit.school_loc[0], first_exit.school_loc[1])
                        if tgt_b4_end + tt <= exit_start:
                            gap = exit_start - (tgt_b4_end + tt)
                            if gap < best_gap:
                                best_gap = gap
                                best_target = tgt_idx
                    else:
                        tgt_end = _get_latest_end(tgt, b1_jobs, b2_jobs, b3_jobs, b4_jobs)
                        if tgt_end[0] is None or tgt_end[1] is None:
                            continue

                        tt = get_travel_time(tgt_end[1][0], tgt_end[1][1],
                                             first_exit.school_loc[0], first_exit.school_loc[1])
                        arrival = tgt_end[0] + tt
                        if arrival <= exit_start:
                            gap = exit_start - arrival
                            if gap < best_gap:
                                best_gap = gap
                                best_target = tgt_idx

                if best_target is not None:
                    tgt = buses[best_target]
                    if tgt.block4_chain:
                        tgt.block4_chain = tgt.block4_chain + src.block4_chain
                    else:
                        tgt.block4_chain = src.block4_chain
                    src.block4_chain = None
                    merged_away.add(src_idx)
                    progress = True

            # ── Bus with block2+block4 but no block1 → try merging into bus with block1 ──
            if src.block2_chain and not src.block1_chain:
                first_exit = b2_jobs[src.block2_chain[0]]
                exit_start = first_exit.time_minutes

                best_target = None
                best_gap = float('inf')

                for tgt_idx in range(len(buses)):
                    if tgt_idx in merged_away or tgt_idx == src_idx:
                        continue
                    tgt = buses[tgt_idx]
                    if tgt.block2_chain:
                        continue  # Already has block2, can't replace
                    if not tgt.block1_chain:
                        continue  # Want to merge INTO a bus with morning entries

                    tgt_end = _get_latest_end(tgt, b1_jobs, b2_jobs, b3_jobs, b4_jobs)
                    if tgt_end[0] is None or tgt_end[1] is None:
                        continue

                    tt = get_travel_time(tgt_end[1][0], tgt_end[1][1],
                                         first_exit.school_loc[0], first_exit.school_loc[1])
                    arrival = tgt_end[0] + tt
                    if arrival <= exit_start and (exit_start - tgt_end[0]) < MAX_CONSOLIDATION_GAP:
                        gap = exit_start - arrival
                        if gap < best_gap:
                            best_gap = gap
                            best_target = tgt_idx

                if best_target is not None:
                    tgt = buses[best_target]
                    tgt.block2_chain = src.block2_chain
                    src.block2_chain = None
                    if src.block3_chain and not tgt.block3_chain:
                        tgt.block3_chain = src.block3_chain
                        src.block3_chain = None
                    if src.block4_chain and not tgt.block4_chain:
                        tgt.block4_chain = src.block4_chain
                        src.block4_chain = None
                    if not src.block1_chain and not src.block2_chain and not src.block3_chain and not src.block4_chain:
                        merged_away.add(src_idx)
                    progress = True

        if not progress:
            break

    # Remove fully merged buses
    result = [b for i, b in enumerate(buses) if i not in merged_away]
    if merged_away:
        print(f"  Consolidation: absorbed {len(merged_away)} partial buses (pass {pass_num + 1})")
    return result


def _get_latest_end(
    bus: BusChain, 
    b1_jobs: List[RouteJob], 
    b2_jobs: List[RouteJob], 
    b3_jobs: List[RouteJob], 
    b4_jobs: List[RouteJob]
) -> Tuple[Optional[int], Optional[Tuple[float, float]]]:
    """Get the latest end time and location across all blocks of a bus."""
    latest_time: Optional[int] = None
    latest_loc: Optional[Tuple[float, float]] = None

    for block_key, jobs, is_entry in [
        ("block4_chain", b4_jobs, False),
        ("block3_chain", b3_jobs, True),
        ("block2_chain", b2_jobs, False),
        ("block1_chain", b1_jobs, True),
    ]:
        chain: Optional[List[int]] = getattr(bus, block_key, None)
        if chain and jobs:
            last_job = jobs[chain[-1]]
            if is_entry:
                end = last_job.time_minutes
                loc = last_job.school_loc
            else:
                end = last_job.time_minutes + last_job.duration_minutes
                loc = last_job.last_stop
            if latest_time is None or end > latest_time:
                latest_time = end
                latest_loc = loc

    return (latest_time, latest_loc)


def _find_best_exit_chain(
    end_time: int, 
    end_loc: Tuple[float, float], 
    chains: List[List[int]], 
    jobs: List[RouteJob], 
    used_set: Set[int]
) -> Tuple[Optional[int], float]:
    """Find best exit chain that can follow the given end time/location."""
    best_c: Optional[int] = None
    best_gap = float('inf')

    for c_idx, chain in enumerate(chains):
        if c_idx in used_set:
            continue
        first_job = jobs[chain[0]]
        tt = get_travel_time(end_loc[0], end_loc[1], first_job.school_loc[0], first_job.school_loc[1])
        arrival = end_time + tt
        if arrival <= first_job.time_minutes:
            gap = first_job.time_minutes - arrival
            if gap < best_gap:
                best_gap = gap
                best_c = c_idx

    return best_c, best_gap


def _find_best_entry_chain(
    end_time: int, 
    end_loc: Tuple[float, float], 
    chains: List[List[int]], 
    jobs: List[RouteJob], 
    used_set: Set[int]
) -> Tuple[Optional[int], float]:
    """Find best entry chain that can follow the given end time/location."""
    best_c: Optional[int] = None
    best_gap = float('inf')

    for c_idx, chain in enumerate(chains):
        if c_idx in used_set:
            continue
        first_job = jobs[chain[0]]
        tt = get_travel_time(end_loc[0], end_loc[1], first_job.first_stop[0], first_job.first_stop[1])
        # Entry chain starts at: first_job.time_minutes - duration - early_shift
        earliest_start = first_job.time_minutes - first_job.duration_minutes - MAX_EARLY_ARRIVAL_MINUTES
        arrival = end_time + tt
        if arrival <= earliest_start + 5:
            gap = earliest_start - arrival
            if gap < best_gap:
                best_gap = gap
                best_c = c_idx

    return best_c, best_gap


# ============================================================
# SCHEDULE CONSTRUCTION
# ============================================================

def compute_effective_arrivals(
    chain: List[int], 
    jobs: List[RouteJob], 
    travel_times: Dict[Tuple[int, int], int]
) -> List[int]:
    """Compute effective arrival times for an entry chain."""
    if not chain:
        return []
    n = len(chain)
    arrivals = [0] * n

    if n == 1:
        arrivals[0] = jobs[chain[0]].time_minutes
        return arrivals

    # Forward pass: shift first as early as possible
    first_job = jobs[chain[0]]
    first_earliest = first_job.time_minutes - MAX_EARLY_ARRIVAL_MINUTES
    if first_earliest - first_job.duration_minutes < 6 * 60:
        first_earliest = 6 * 60 + first_job.duration_minutes
    arrivals[0] = min(first_earliest, first_job.time_minutes)

    for i in range(1, n):
        prev_idx = chain[i - 1]
        curr_idx = chain[i]
        curr_job = jobs[curr_idx]
        tt = travel_times.get((prev_idx, curr_idx), 20)

        earliest_start = arrivals[i - 1] + tt
        min_arrival = earliest_start + curr_job.duration_minutes
        max_arrival = curr_job.time_minutes

        effective = max(min_arrival, curr_job.time_minutes - MAX_EARLY_ARRIVAL_MINUTES)
        effective = min(effective, max_arrival)
        arrivals[i] = effective

    return arrivals


def compute_effective_departures(
    chain: List[int], 
    jobs: List[RouteJob], 
    travel_times: Dict[Tuple[int, int], int]
) -> List[int]:
    """Compute effective departure times for an exit chain with ±5min shift."""
    if not chain:
        return []
    n = len(chain)
    departures = [0] * n

    if n == 1:
        # Primera ruta: puede salir hasta 5 min antes
        departures[0] = jobs[chain[0]].time_minutes - MAX_EXIT_SHIFT_MINUTES
        return departures

    # Primera ruta: puede salir hasta 5 min antes
    first_job = jobs[chain[0]]
    departures[0] = first_job.time_minutes - MAX_EXIT_SHIFT_MINUTES

    for i in range(1, n):
        prev_idx = chain[i - 1]
        curr_idx = chain[i]
        curr_job = jobs[curr_idx]
        tt = travel_times.get((prev_idx, curr_idx), 20)

        # El bus llega a la escuela de la ruta i
        prev_end = departures[i - 1] + jobs[prev_idx].duration_minutes
        arrival_at_school = prev_end + tt

        # Effective departure: max(prev_end + tt, time_j - 5), clamped a [time_j - 5, time_j + 5]
        effective = max(arrival_at_school, curr_job.time_minutes - MAX_EXIT_SHIFT_MINUTES)
        effective = min(effective, curr_job.time_minutes + MAX_EXIT_SHIFT_MINUTES)
        departures[i] = effective

    return departures


def build_full_schedule(
    bus_chains: List[BusChain],
    b1_jobs: List[RouteJob], b1_tt: Dict[Tuple[int, int], int],
    b2_jobs: List[RouteJob], b2_tt: Dict[Tuple[int, int], int],
    b3_jobs: List[RouteJob], b3_tt: Dict[Tuple[int, int], int],
    b4_jobs: List[RouteJob], b4_tt: Dict[Tuple[int, int], int],
) -> List[BusSchedule]:
    """Build final BusSchedule objects from BusChain objects."""

    schedules: List[BusSchedule] = []

    for bus_num, bus_chain in enumerate(bus_chains):
        items: List[ScheduleItem] = []
        bus_id = f"B{bus_num + 1:03d}"

        # Block 1: Morning entries
        if bus_chain.block1_chain:
            arrivals = compute_effective_arrivals(bus_chain.block1_chain, b1_jobs, b1_tt)
            for i, idx in enumerate(bus_chain.block1_chain):
                job = b1_jobs[idx]
                eff_arrival = arrivals[i]
                start = eff_arrival - job.duration_minutes
                shift = job.time_minutes - eff_arrival
                deadhead = b1_tt.get((bus_chain.block1_chain[i - 1], idx), 0) if i > 0 else 0
                items.append(_make_item(job, start, eff_arrival, shift, deadhead))

        # Block 2: Early exits
        if bus_chain.block2_chain:
            departures = compute_effective_departures(bus_chain.block2_chain, b2_jobs, b2_tt)
            for i, idx in enumerate(bus_chain.block2_chain):
                job = b2_jobs[idx]
                eff_departure = departures[i]
                end = eff_departure + job.duration_minutes
                shift = eff_departure - job.time_minutes  # Puede ser negativo (sale antes)
                deadhead = b2_tt.get((bus_chain.block2_chain[i - 1], idx), 0) if i > 0 else 0
                items.append(_make_item(job, eff_departure, end, shift, deadhead))

        # Block 3: Late entries
        if bus_chain.block3_chain:
            arrivals = compute_effective_arrivals(bus_chain.block3_chain, b3_jobs, b3_tt)
            for i, idx in enumerate(bus_chain.block3_chain):
                job = b3_jobs[idx]
                eff_arrival = arrivals[i]
                start = eff_arrival - job.duration_minutes
                shift = job.time_minutes - eff_arrival
                deadhead = b3_tt.get((bus_chain.block3_chain[i - 1], idx), 0) if i > 0 else 0
                items.append(_make_item(job, start, eff_arrival, shift, deadhead))

        # Block 4: Late exits
        if bus_chain.block4_chain:
            departures = compute_effective_departures(bus_chain.block4_chain, b4_jobs, b4_tt)
            for i, idx in enumerate(bus_chain.block4_chain):
                job = b4_jobs[idx]
                eff_departure = departures[i]
                end = eff_departure + job.duration_minutes
                shift = eff_departure - job.time_minutes  # Puede ser negativo (sale antes)
                deadhead = b4_tt.get((bus_chain.block4_chain[i - 1], idx), 0) if i > 0 else 0
                items.append(_make_item(job, eff_departure, end, shift, deadhead))

        if items:
            schedules.append(BusSchedule(bus_id=bus_id, items=items))

    return schedules


def _reverse_exit_stops(stops: List[Stop]) -> List[Stop]:
    """Reverse stops for exit routes: school -> drop-off stops."""
    if not stops or len(stops) < 2:
        return stops
    total_duration = max(s.time_from_start for s in stops)
    reversed_stops: List[Stop] = []
    for s in reversed(stops):
        new_stop = Stop(
            name=s.name, lat=s.lat, lon=s.lon,
            order=len(stops) - s.order + 1,
            time_from_start=total_duration - s.time_from_start,
            passengers=s.passengers, is_school=s.is_school
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
    stops = _reverse_exit_stops(job.route.stops) if job.route_type == "exit" else job.route.stops

    return ScheduleItem(
        route_id=job.route.id,
        start_time=from_minutes(start_mins),
        end_time=from_minutes(end_mins),
        type=job.route_type,
        school_name=job.school_name,
        stops=stops,
        contract_id=job.route.contract_id,
        original_start_time=job.route.arrival_time if job.route_type == "entry" else job.route.departure_time,
        time_shift_minutes=max(0, shift),
        deadhead_minutes=deadhead
    )


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def optimize_v5(routes: List[Route]) -> List[BusSchedule]:
    """
    Main optimization function for V5.
    
    Args:
        routes: List of Route objects to optimize
        
    Returns:
        List of BusSchedule objects representing the optimized fleet
    """
    print("\n" + "=" * 60)
    print("TUTTI OPTIMIZER V5")
    print("=" * 60)

    # Phase 1: Prepare
    print("\n[Phase 1] Preparing route jobs...")
    blocks = prepare_jobs(routes)
    for b in [1, 2, 3, 4]:
        block_type = {1: "Morning entries", 2: "Early exits", 3: "Late entries", 4: "Late exits"}[b]
        print(f"  Block {b} ({block_type}): {len(blocks[b])} routes")

    # Phase 2: Precompute travel matrices per block
    print("\n[Phase 2] Computing travel time matrices...")
    b1_tt = precompute_travel_matrix_for_block(blocks[1], is_entry=True) if blocks[1] else {}
    b2_tt = precompute_travel_matrix_for_block(blocks[2], is_entry=False) if blocks[2] else {}
    b3_tt = precompute_travel_matrix_for_block(blocks[3], is_entry=True) if blocks[3] else {}
    b4_tt = precompute_travel_matrix_for_block(blocks[4], is_entry=False) if blocks[4] else {}
    save_cache()

    # Phase 3: Build chains per block
    print("\n[Phase 3] Building chains per block...")
    b1_chains = build_entry_chains(blocks[1], b1_tt) if blocks[1] else []
    b2_chains = build_exit_chains(blocks[2], b2_tt) if blocks[2] else []
    b3_chains = build_entry_chains(blocks[3], b3_tt) if blocks[3] else []
    b4_chains = build_exit_chains(blocks[4], b4_tt) if blocks[4] else []

    for b, chains, name in [(1, b1_chains, "Morning entries"), (2, b2_chains, "Early exits"),
                             (3, b3_chains, "Late entries"), (4, b4_chains, "Late exits")]:
        if chains:
            sizes = [len(c) for c in chains]
            print(f"  Block {b} ({name}): {len(chains)} chains, sizes: {min(sizes)}-{max(sizes)}, avg={sum(sizes)/len(sizes):.1f}")
        else:
            print(f"  Block {b} ({name}): 0 chains")

    # Phase 4: Merge blocks
    print("\n[Phase 4] Merging blocks...")
    bus_chains = merge_blocks_v2(
        b1_chains, blocks[1],
        b2_chains, blocks[2],
        b3_chains, blocks[3],
        b4_chains, blocks[4],
    )
    print(f"  Total buses after merge: {len(bus_chains)}")

    # Diagnostic: count bus types
    b1_only = sum(1 for b in bus_chains if b.block1_chain and not b.block2_chain and not b.block3_chain and not b.block4_chain)
    b2_only = sum(1 for b in bus_chains if b.block2_chain and not b.block1_chain and not b.block3_chain and not b.block4_chain)
    b1_b2 = sum(1 for b in bus_chains if b.block1_chain and b.block2_chain)
    print(f"  Bus breakdown: {b1_only} entry-only, {b2_only} exit-only, {b1_b2} entry+exit, {len(bus_chains)} total")

    # Phase 5: Build schedules
    print("\n[Phase 5] Building final schedules...")
    buses = build_full_schedule(
        bus_chains,
        blocks[1], b1_tt,
        blocks[2], b2_tt,
        blocks[3], b3_tt,
        blocks[4], b4_tt,
    )

    # Remove empty buses
    buses = [b for b in buses if b.items]

    # Renumber
    for i, bus in enumerate(buses):
        bus.bus_id = f"B{i+1:03d}"

    # Statistics
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    total_routes = sum(len(b.items) for b in buses)
    entry_count = sum(1 for b in buses for item in b.items if item.type == "entry")
    exit_count = sum(1 for b in buses for item in b.items if item.type == "exit")
    routes_per_bus = [len(b.items) for b in buses]

    print(f"  Total buses: {len(buses)}")
    print(f"  Total routes assigned: {total_routes}")
    print(f"  Entries: {entry_count}, Exits: {exit_count}")
    if routes_per_bus:
        print(f"  Routes/bus: min={min(routes_per_bus)}, max={max(routes_per_bus)}, avg={sum(routes_per_bus)/len(routes_per_bus):.1f}")

    # Per-bus summary
    for bus in buses:
        entries_in = [i for i in bus.items if i.type == "entry"]
        exits_in = [i for i in bus.items if i.type == "exit"]
        schools = set(i.school_name for i in bus.items)
        shifts = [i.time_shift_minutes for i in entries_in if i.time_shift_minutes > 0]
        shift_str = f", shifts: {shifts}" if shifts else ""
        print(f"  {bus.bus_id}: {len(entries_in)}E + {len(exits_in)}X = {len(bus.items)} total, {len(schools)} schools{shift_str}")

    print("=" * 60)
    return buses


def optimize_routes_v5(routes: List[Route]) -> List[BusSchedule]:
    """Alias for optimize_v5."""
    return optimize_v5(routes)


__all__ = ['optimize_v5', 'optimize_routes_v5']
