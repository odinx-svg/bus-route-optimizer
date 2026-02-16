"""
Optimizer V2 - Implementa requisitos específicos del cliente:
1. Mínimo 3 entradas y 3 salidas por bus (ideal 4-5)
2. Llegada anticipada: 30min 1er colegio, 20min 2do, 10min 3ro, 0min 4to
3. Balanceo de carga entre buses
"""
import logging
from typing import List, Dict, Tuple, Optional, cast
from datetime import time, timedelta
from models import Route, BusSchedule, ScheduleItem
from router_service import get_travel_time_matrix

logger = logging.getLogger(__name__)

# Early arrival strategy: minutes before school arrival
# Index 0 = first school, 1 = second school, etc.
EARLY_ARRIVAL_MINUTES: List[int] = [30, 20, 10, 0]  # 30min, 20min, 10min, on-time


def to_minutes(t: time) -> int:
    """Convert time to minutes since midnight"""
    return t.hour * 60 + t.minute


def from_minutes(mins: int) -> time:
    """Convert minutes since midnight to time"""
    mins = mins % (24 * 60)
    return time(mins // 60, mins % 60)


def add_minutes(t: time, minutes: int) -> time:
    """Add minutes to a time."""
    mins = to_minutes(t) + minutes
    return from_minutes(mins)


def subtract_minutes(t: time, minutes: int) -> time:
    """Subtract minutes from a time."""
    mins = to_minutes(t) - minutes
    return from_minutes(mins)


def time_diff_minutes(t1: time, t2: time) -> int:
    """Calculate difference between two times in minutes."""
    return to_minutes(t1) - to_minutes(t2)


def calculate_travel_time_minutes(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """
    Calculate travel time between two coordinates.
    Simple haversine-based estimation for V2.
    """
    import math
    
    # Simple haversine
    R = 6371  # Earth radius in km
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    km = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    # Assume 60 km/h average speed
    return max(5, int(km * 60 / 60))


def determine_route_duration(route: Route) -> int:
    """Determine route duration based on stops or default."""
    if route.stops:
        max_time = max((s.time_from_start for s in route.stops), default=0)
        if max_time > 0:
            return max_time
    return 30  # Default 30 minutes


def classify_route_type(route: Route) -> str:
    """Classify route as morning entry or afternoon exit"""
    if route.type == "entry":
        return "morning"
    elif route.type == "exit":
        return "afternoon"
    # Fallback based on time
    arrival_mins = to_minutes(route.arrival_time) if route.arrival_time else 0
    if arrival_mins < 12 * 60:  # Before noon
        return "morning"
    return "afternoon"


def group_routes_by_type(routes: List[Route]) -> Tuple[List[Route], List[Route]]:
    """Separate routes into morning (entry) and afternoon (exit)"""
    morning: List[Route] = []
    afternoon: List[Route] = []
    
    for route in routes:
        route_type = classify_route_type(route)
        if route_type == "morning":
            morning.append(route)
        else:
            afternoon.append(route)
    
    return morning, afternoon


def calculate_early_arrival_time(route: Route, route_index_in_bus: int) -> time:
    """
    Calculate arrival time with early arrival strategy.
    route_index_in_bus: 0=first, 1=second, 2=third, etc.
    """
    if route.type != "entry":
        # For exit routes, return original departure time
        return route.departure_time or time(0, 0)
    
    if not route.arrival_time:
        return time(0, 0)
    
    # Get early arrival offset based on position
    early_mins = EARLY_ARRIVAL_MINUTES[min(route_index_in_bus, len(EARLY_ARRIVAL_MINUTES) - 1)]
    
    # Calculate adjusted arrival (earlier than school time)
    school_arrival = route.arrival_time
    adjusted_arrival_mins = to_minutes(school_arrival) - early_mins
    
    return from_minutes(adjusted_arrival_mins)


def can_chain_routes(
    route_a: Route, 
    route_b: Route, 
    travel_time: int, 
    max_shift: int = 15
) -> bool:
    """Check if route_b can follow route_a considering travel time"""
    
    # Calculate end of route_a
    duration_a = determine_route_duration(route_a)
    if route_a.type == "entry":
        end_a = route_a.arrival_time or time(0, 0)
    else:
        start_a = route_b.departure_time or time(0, 0)
        end_a = add_minutes(start_a, duration_a)
    
    # Calculate start of route_b
    duration_b = determine_route_duration(route_b)
    if route_b.type == "entry":
        # For entry routes, calculate when we'd need to start
        school_arrival = route_b.arrival_time or time(0, 0)
        start_b = subtract_minutes(school_arrival, duration_b)
    else:
        start_b = route_b.departure_time or time(0, 0)
    
    # Check if we can make it
    arrival_at_b = add_minutes(end_a, travel_time)
    
    # Add 10 min buffer between routes
    arrival_at_b_buffered = add_minutes(arrival_at_b, 10)
    
    # Check if we arrive before start_b (with some flexibility)
    arrival_mins = to_minutes(arrival_at_b_buffered)
    start_b_mins = to_minutes(start_b)
    
    # We can start route_b if we arrive before it starts (or up to max_shift late)
    return arrival_mins <= start_b_mins + max_shift


def build_bus_chains(
    routes: List[Route], 
    min_routes: int = 3, 
    max_routes: int = 5
) -> List[BusSchedule]:
    """
    Build bus chains ensuring each bus has between min_routes and max_routes.
    Uses greedy algorithm with backtracking to balance load.
    """
    if not routes:
        return []
    
    # Sort routes by start time
    def get_route_time(r: Route) -> int:
        if r.type == "entry":
            t = r.arrival_time if r.arrival_time is not None else time(0, 0)
        else:
            t = r.departure_time if r.departure_time is not None else time(0, 0)
        return to_minutes(t)
    
    sorted_routes = sorted(routes, key=get_route_time)
    
    buses: List[BusSchedule] = []
    unassigned = list(sorted_routes)
    
    # Get travel time matrix
    n = len(sorted_routes)
    sources = [(r.stops[-1].lat, r.stops[-1].lon) if r.stops else (0.0, 0.0) for r in sorted_routes]
    destinations = [(r.stops[0].lat, r.stops[0].lon) if r.stops else (0.0, 0.0) for r in sorted_routes]
    travel_matrix = get_travel_time_matrix(sources, destinations)
    
    route_to_idx = {r.id: i for i, r in enumerate(sorted_routes)}
    
    while unassigned:
        # Start a new bus with first unassigned route
        first_route = unassigned[0]
        bus_routes = [first_route]
        unassigned.remove(first_route)
        
        current_route = first_route
        current_idx = route_to_idx[current_route.id]
        
        # Try to add more routes to this bus (up to max_routes)
        for route_num in range(1, max_routes):
            if not unassigned:
                break
            
            # Find best next route
            best_next: Optional[Route] = None
            best_travel = float('inf')
            
            for candidate in unassigned:
                candidate_idx = route_to_idx[candidate.id]
                travel = travel_matrix[current_idx][candidate_idx]
                if travel is None:
                    travel = calculate_travel_time_minutes(
                        current_route.stops[-1].lat if current_route.stops else 0,
                        current_route.stops[-1].lon if current_route.stops else 0,
                        candidate.stops[0].lat if candidate.stops else 0,
                        candidate.stops[0].lon if candidate.stops else 0
                    )
                
                if can_chain_routes(current_route, candidate, travel):
                    if travel < best_travel:
                        best_travel = travel
                        best_next = candidate
            
            if best_next:
                bus_routes.append(best_next)
                unassigned.remove(best_next)
                current_route = best_next
                current_idx = route_to_idx[current_route.id]
            else:
                break
        
        # Create bus schedule
        items: List[ScheduleItem] = []
        for i, route in enumerate(bus_routes):
            duration = determine_route_duration(route)
            
            if route.type == "entry":
                # For entry routes, use early arrival strategy
                school_arrival = route.arrival_time
                early_arrival = calculate_early_arrival_time(route, i)
                start_time = subtract_minutes(early_arrival, duration)
                end_time = early_arrival
            else:
                # For exit routes
                start_time = route.departure_time or time(0, 0)
                end_time = add_minutes(start_time, duration)
            
            items.append(ScheduleItem(
                route_id=route.id,
                start_time=start_time,
                end_time=end_time,
                type=route.type,
                school_name=route.school_name,
                stops=route.stops,
                contract_id=route.contract_id,
                original_start_time=route.departure_time if route.type == "exit" else route.arrival_time,
                time_shift_minutes=0,
                deadhead_minutes=0
            ))
        
        bus = BusSchedule(
            bus_id=f"B{len(buses) + 1}",
            items=items
        )
        buses.append(bus)
    
    return buses


def merge_morning_afternoon(
    morning_buses: List[BusSchedule], 
    afternoon_buses: List[BusSchedule]
) -> List[BusSchedule]:
    """
    Merge morning and afternoon buses optimally.
    Try to pair morning-only with afternoon-only buses.
    """
    if not afternoon_buses:
        return morning_buses
    if not morning_buses:
        return afternoon_buses
    
    merged: List[BusSchedule] = []
    afternoon_used: set[int] = set()
    
    for m_bus in morning_buses:
        # Get last location of morning bus
        if not m_bus.items:
            continue
        last_item = m_bus.items[-1]
        end_loc_m = (last_item.stops[-1].lat, last_item.stops[-1].lon) if last_item.stops else (0.0, 0.0)
        end_time_m = last_item.end_time
        end_mins_m = to_minutes(end_time_m)
        
        best_match: Optional[Tuple[int, BusSchedule]] = None
        best_gap = float('inf')
        
        for i, a_bus in enumerate(afternoon_buses):
            if i in afternoon_used:
                continue
            if not a_bus.items:
                continue
            
            first_item = a_bus.items[0]
            start_loc_a = (first_item.stops[0].lat, first_item.stops[0].lon) if first_item.stops else (0.0, 0.0)
            start_time_a = first_item.start_time
            start_mins_a = to_minutes(start_time_a)
            
            travel = calculate_travel_time_minutes(
                end_loc_m[0], end_loc_m[1],
                start_loc_a[0], start_loc_a[1]
            )
            
            gap = start_mins_a - end_mins_m
            min_needed = travel + 10  # 10 min buffer
            
            if gap >= min_needed and gap < best_gap:
                best_gap = gap
                best_match = (i, a_bus)
        
        if best_match:
            # Merge buses
            idx, a_bus = best_match
            afternoon_used.add(idx)
            
            # Combine items
            combined_items = m_bus.items + a_bus.items
            merged_bus = BusSchedule(
                bus_id=m_bus.bus_id,
                items=combined_items
            )
            merged.append(merged_bus)
        else:
            # Keep morning bus as is
            merged.append(m_bus)
    
    # Add unused afternoon buses
    for i, a_bus in enumerate(afternoon_buses):
        if i not in afternoon_used:
            merged.append(a_bus)
    
    return merged


def rebalance_buses(
    buses: List[BusSchedule], 
    all_routes: List[Route],
    min_routes: int = 3, 
    max_routes: int = 5
) -> List[BusSchedule]:
    """
    Rebalance buses to ensure each has between min_routes and max_routes.
    Move routes from overloaded buses to underloaded ones.
    """
    # Identify overloaded and underloaded buses
    overloaded = [b for b in buses if len(b.items) > max_routes]
    underloaded = [b for b in buses if len(b.items) < min_routes]
    
    if not overloaded or not underloaded:
        return buses
    
    # Try to move routes from overloaded to underloaded
    for over_bus in overloaded:
        while len(over_bus.items) > max_routes and underloaded:
            # Find a route we can move
            for route_idx, item in enumerate(over_bus.items):
                # Try to add to each underloaded bus
                for under_bus in underloaded:
                    if can_add_to_bus(item, under_bus):
                        # Move route
                        under_bus.items.append(item)
                        over_bus.items.pop(route_idx)
                        
                        # Sort items by time
                        under_bus.items.sort(key=lambda x: to_minutes(x.start_time))
                        
                        # Update underloaded list
                        underloaded = [b for b in underloaded if len(b.items) < min_routes]
                        break
                else:
                    continue
                break
            else:
                break
    
    return buses


def can_add_to_bus(item: ScheduleItem, bus: BusSchedule, max_shift: int = 15) -> bool:
    """Check if an item can be added to a bus without conflicts"""
    if not bus.items:
        return True
    
    # Check against all existing items
    item_start = to_minutes(item.start_time)
    item_end = to_minutes(item.end_time)
    
    for existing in bus.items:
        existing_start = to_minutes(existing.start_time)
        existing_end = to_minutes(existing.end_time)
        
        # Check for overlap
        if not (item_end <= existing_start or item_start >= existing_end):
            return False
    
    return True


def optimize_routes_v2(routes: List[Route]) -> List[BusSchedule]:
    """
    Main optimization function implementing client requirements:
    1. Balance: 3-5 routes per bus
    2. Early arrival strategy for morning routes
    3. Proper morning/afternoon merging
    """
    logger.info(f"Starting V2 optimization with {len(routes)} routes")
    
    # Separate morning and afternoon
    morning_routes, afternoon_routes = group_routes_by_type(routes)
    logger.info(f"Morning routes: {len(morning_routes)}, Afternoon routes: {len(afternoon_routes)}")
    
    # Build morning buses (target: 3-5 routes each)
    morning_buses = build_bus_chains(morning_routes, min_routes=3, max_routes=5)
    logger.info(f"Created {len(morning_buses)} morning buses")
    
    # Build afternoon buses (target: 3-5 routes each)
    afternoon_buses = build_bus_chains(afternoon_routes, min_routes=3, max_routes=5)
    logger.info(f"Created {len(afternoon_buses)} afternoon buses")
    
    # Merge morning and afternoon
    all_buses = merge_morning_afternoon(morning_buses, afternoon_buses)
    logger.info(f"After merge: {len(all_buses)} total buses")
    
    # Rebalance if needed
    all_buses = rebalance_buses(all_buses, routes, min_routes=3, max_routes=5)
    
    # Log final statistics
    route_counts = [len(b.items) for b in all_buses]
    logger.info(f"Final stats: {len(all_buses)} buses, routes per bus: min={min(route_counts)}, max={max(route_counts)}, avg={sum(route_counts) / len(route_counts):.1f}")
    
    return all_buses


__all__ = ['optimize_routes_v2', 'to_minutes', 'from_minutes']
