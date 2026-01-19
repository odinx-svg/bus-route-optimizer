import math
from datetime import datetime, timedelta, time
from typing import List, Tuple
from models import Route, Bus, BusSchedule, ScheduleItem

# LP optimizer dependency
try:
    import pulp
except ImportError:
    pulp = None  # Will be installed via dependencies.txt

# Constants
AVERAGE_SPEED_KMH = 45  # Increased from 40 to 45 km/h
TORTUOSITY_FACTOR = 1.2  # Decreased from 1.4 to 1.2 (assumes straighter roads)
EARTH_RADIUS_KM = 6371

def haversine_distance(lat1, lon1, lat2, lon2):
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) * math.sin(dlat / 2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dlon / 2) * math.sin(dlon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c

def calculate_travel_time_minutes(lat1, lon1, lat2, lon2):
    dist_km = haversine_distance(lat1, lon1, lat2, lon2) * TORTUOSITY_FACTOR
    time_hours = dist_km / AVERAGE_SPEED_KMH
    return int(time_hours * 60) + 2 # Reduced buffer from 5 to 2 mins

def add_minutes(t: time, minutes: int) -> time:
    dt = datetime.combine(datetime.today(), t)
    return (dt + timedelta(minutes=minutes)).time()

def subtract_minutes(t: time, minutes: int) -> time:
    dt = datetime.combine(datetime.today(), t)
    return (dt - timedelta(minutes=minutes)).time()

def time_diff_minutes(t1: time, t2: time) -> int:
    # t1 - t2
    dt1 = datetime.combine(datetime.today(), t1)
    dt2 = datetime.combine(datetime.today(), t2)
    return int((dt1 - dt2).total_seconds() / 60)

def optimize_routes(routes: List[Route]) -> List[BusSchedule]:
    # 1. Convert all routes to "Jobs"
    jobs = []
    
    for route in routes:
        # Calculate duration
        route_duration = 30 # Default
        dist_km = 0
        if route.stops and len(route.stops) > 1:
            d = 0
            for k in range(len(route.stops)-1):
                d += haversine_distance(route.stops[k].lat, route.stops[k].lon, route.stops[k+1].lat, route.stops[k+1].lon)
            dist_km = d * TORTUOSITY_FACTOR
            route_duration = int((dist_km / AVERAGE_SPEED_KMH) * 60) + (len(route.stops) * 1) # +1 min per stop
            
        if route.type == "entry":
            # Entry: Start at First Stop, End at School
            # We need School Coords. If not present, assume Last Stop (which is wrong for entry, usually school is destination)
            # But in the provided data, "Parada destino" is the school.
            # Let's assume the route.stops[-1] is close to school or IS the school if we parsed it that way.
            # Actually, for Entry, the last stop IS the school usually.
            
            start_time = subtract_minutes(route.arrival_time, route_duration)
            end_time = route.arrival_time
            
            start_loc = (0,0)
            end_loc = (0,0)
            if route.stops:
                start_loc = (route.stops[0].lat, route.stops[0].lon)
                end_loc = (route.stops[-1].lat, route.stops[-1].lon)
                
            jobs.append({
                "route": route,
                "start_time": start_time,
                "end_time": end_time,
                "start_loc": start_loc,
                "end_loc": end_loc,
                "type": "entry"
            })
            
        elif route.type == "exit":
            # Exit: Start at School, End at Last Stop
            # Start Time = Departure Time
            if not route.departure_time:
                continue # Skip if no time
                
            start_time = route.departure_time
            end_time = add_minutes(start_time, route_duration)
            
            start_loc = (0,0)
            end_loc = (0,0)
            if route.stops:
                start_loc = (route.stops[0].lat, route.stops[0].lon) # School
                end_loc = (route.stops[-1].lat, route.stops[-1].lon) # Last drop off
            
            jobs.append({
                "route": route,
                "start_time": start_time,
                "end_time": end_time,
                "start_loc": start_loc,
                "end_loc": end_loc,
                "type": "exit"
            })

    # 2. Sort jobs by start time
    jobs.sort(key=lambda x: x["start_time"])
    
    buses = []
    
    # 3. Greedy Assignment
    for job in jobs:
        best_bus_idx = -1
        min_deadhead = float('inf')
        
        for i, bus_schedule in enumerate(buses):
            last_item = bus_schedule.items[-1]
            
            # Get last job's end location
            # We need to store end_loc in schedule item or look it up
            # For simplicity, let's look up the job that corresponds to last_item
            # But schedule item is simple.
            # Let's store end_loc in the bus object temporarily or infer it.
            
            # Optimization: We can store "last_loc" and "last_time" on the bus object (in memory)
            last_loc = getattr(bus_schedule, "last_loc", (0,0))
            last_time = bus_schedule.items[-1].end_time
            
            # Calculate travel from last_loc to job['start_loc']
            travel_time = calculate_travel_time_minutes(
                last_loc[0], last_loc[1],
                job['start_loc'][0], job['start_loc'][1]
            )
            
            arrival_at_start = add_minutes(last_time, travel_time)
            
            # Check feasibility
            if time_diff_minutes(job['start_time'], arrival_at_start) >= 0:
                deadhead = time_diff_minutes(job['start_time'], arrival_at_start)
                if deadhead < min_deadhead:
                    min_deadhead = deadhead
                    best_bus_idx = i
        
        # Create Schedule Item
        item = ScheduleItem(
            route_id=job['route'].id,
            start_time=job['start_time'],
            end_time=job['end_time'],
            type=job['type']
        )
        
        if best_bus_idx != -1:
            buses[best_bus_idx].items.append(item)
            # Update bus state
            buses[best_bus_idx].last_loc = job['end_loc']
        else:
            new_bus = BusSchedule(
                bus_id=f"B{len(buses)+1}",
                items=[item]
            )
            new_bus.last_loc = job['end_loc'] # Monkey patch for algorithm
            buses.append(new_bus)
            
    # Apply post-processing merging here as well
    return emparejar_turnos_manana_tarde(buses)

# ------------------------------------------------------------
# Exact Optimizer (DAG Path Cover via Max Bipartite Matching)
# ------------------------------------------------------------

# ------------------------------------------------------------
# Exact Optimizer (DAG Path Cover via Max Bipartite Matching)
# ------------------------------------------------------------

from router_service import get_real_travel_time, get_travel_time_matrix

def optimize_routes_lp(routes: List[Route]) -> List[BusSchedule]:
    """
    Optimizes fleet size using a Minimum Path Cover on a DAG.
    Includes OSRM real travel times and +/- 15 min time windows.
    """
    if pulp is None:
        raise ImportError("pulp library is required. Install via dependencies.txt")

    # 1. Prepare Jobs
    jobs = []
    for route in routes:
        # Calculate duration (still using heuristic for route duration itself as we don't have full path)
        # Or we could use OSRM for route duration if we had all points, but stops are usually close.
        # Let's stick to heuristic for *intra-route* duration for now.
        route_duration = 30
        dist_km = 0
        if route.stops and len(route.stops) > 1:
            d = 0
            for k in range(len(route.stops)-1):
                d += haversine_distance(route.stops[k].lat, route.stops[k].lon,
                                         route.stops[k+1].lat, route.stops[k+1].lon)
            dist_km = d * TORTUOSITY_FACTOR
            route_duration = int((dist_km / AVERAGE_SPEED_KMH) * 60) + (len(route.stops) * 1)
        
        start_time = None
        end_time = None
        start_loc = (0,0)
        end_loc = (0,0)
        
        if route.stops:
            start_loc = (route.stops[0].lat, route.stops[0].lon)
            end_loc = (route.stops[-1].lat, route.stops[-1].lon)

        if route.type == "entry":
            if not route.arrival_time:
                print(f"Skipping route {route.id} (entry) due to missing arrival time")
                continue
            start_time = subtract_minutes(route.arrival_time, route_duration)
            end_time = route.arrival_time
        elif route.type == "exit":
            if not route.departure_time:
                print(f"Skipping route {route.id} (exit) due to missing departure time")
                continue
            start_time = route.departure_time
            end_time = add_minutes(start_time, route_duration)
        else:
            continue
            
        jobs.append({
            "id": route.id,
            "route": route,
            "start_time": start_time,
            "end_time": end_time,
            "start_loc": start_loc,
            "end_loc": end_loc,
            "type": route.type,
            "type": route.type,
            "original_start": start_time, # Keep track
            "index": len(jobs) # Store index for matrix lookup
        })

    n_jobs = len(jobs)
    print(f"DEBUG: Optimization started for {n_jobs} jobs.")

    # 2. Build Feasible Transitions (Edges) with Time Windows & OSRM
    feasible_edges = []
    edge_weights = {} # (i, j) -> weight
    
    # Prepare sources (end locations) and destinations (start locations)
    sources = [job["end_loc"] for job in jobs]
    destinations = [job["start_loc"] for job in jobs]
    
    print(f"DEBUG: Fetching travel time matrix for {n_jobs} jobs...")
    travel_time_matrix = get_travel_time_matrix(sources, destinations)
    print("DEBUG: Matrix fetch complete.")
    
    osrm_calls = 0 
    skipped_calls = 0
    
    print(f"DEBUG: Starting pair analysis for {n_jobs} jobs ({n_jobs*n_jobs} pairs)...")
    
    for i in range(n_jobs):
        for j in range(n_jobs):
            if i == j: continue
            
            job_a = jobs[i]
            job_b = jobs[j]
            
            # PRE-CHECK: Calculate Haversine time first
            min_travel_time = calculate_travel_time_minutes(
                job_a["end_loc"][0], job_a["end_loc"][1],
                job_b["start_loc"][0], job_b["start_loc"][1]
            )
            
            # Check if this minimum time is already feasible
            min_arrival = add_minutes(job_a["end_time"], min_travel_time)
            
            def to_mins(t): return t.hour * 60 + t.minute
            b_start_mins = to_mins(job_b["start_time"])
            min_arrival_mins = to_mins(min_arrival)
            
            # If even with straight line flight we are late, skip
            if min_arrival_mins > b_start_mins + 15:
                skipped_calls += 1
                continue

            # Use Matrix Lookup
            travel_time = travel_time_matrix[i][j]
            
            if travel_time is None:
                # Fallback to Haversine if matrix failed for this pair
                travel_time = min_travel_time
            
            # Time Window Logic:
            arrival_at_b = add_minutes(job_a["end_time"], travel_time)
            arrival_mins = to_mins(arrival_at_b)
            
            if arrival_mins > b_start_mins + 15:
                continue # Too late
                
            feasible_edges.append((i, j))
            
            # WEIGHT CALCULATION
            # We want to MAXIMIZE the number of edges FIRST, and MINIMIZE deadhead SECOND.
            # Score = (Base Score) - (Deadhead Penalty)
            # Base Score = 1000 (Must be > max possible deadhead)
            # This ensures that adding an edge is always better than not adding one.
            # And among edges, the one with lower deadhead has higher score.
            edge_weights[f"{i}_{j}"] = 1000 - travel_time

    print(f"DEBUG: Found {len(feasible_edges)} feasible transitions.")

    # 3. Solve Max Weight Perfect Matching (or close to it)
    prob = pulp.LpProblem("MaxMatching", pulp.LpMaximize)
    x = pulp.LpVariable.dicts("link", (f"{i}_{j}" for i, j in feasible_edges), cat=pulp.LpBinary)
    
    # Objective: Maximize sum of weights
    prob += pulp.lpSum([x[f"{i}_{j}"] * edge_weights[f"{i}_{j}"] for i, j in feasible_edges])
    
    for i in range(n_jobs):
        outgoing = [f"{i}_{j}" for u, j in feasible_edges if u == i]
        if outgoing: prob += pulp.lpSum([x[k] for k in outgoing]) <= 1
            
    for j in range(n_jobs):
        incoming = [f"{i}_{j}" for i, v in feasible_edges if v == j]
        if incoming: prob += pulp.lpSum([x[k] for k in incoming]) <= 1
            
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    
    # 4. Reconstruct Chains & Apply Time Shifts
    next_job = {}
    has_predecessor = set()
    for i, j in feasible_edges:
        if pulp.value(x[f"{i}_{j}"]) == 1:
            next_job[i] = j
            has_predecessor.add(j)
            
    # Queue of start nodes (roots of chains or broken chains)
    queue = [i for i in range(n_jobs) if i not in has_predecessor]
    bus_schedules = []
    
    # Process queue
    while queue:
        start_idx = queue.pop(0)
        
        # Build the potential chain from this start node
        # We follow next_job until end or until we decide to break
        chain_indices = [start_idx]
        curr = start_idx
        while curr in next_job:
            curr = next_job[curr]
            chain_indices.append(curr)
            
        final_items = []
        last_end_loc = None
        last_end_time = None
        
        # Iterate through the potential chain
        for k, job_idx in enumerate(chain_indices):
            job = jobs[job_idx]
            original_start = job["start_time"]
            duration = time_diff_minutes(job["end_time"], job["start_time"])
            
            actual_start = original_start
            
            if last_end_time:
                # Calculate travel from previous job in this chain
                last_job_idx = chain_indices[k-1]
                curr_job_idx = job_idx
                
                # Use matrix if available
                travel = travel_time_matrix[last_job_idx][curr_job_idx]
                
                if travel is None:
                     last_job = jobs[last_job_idx]
                     travel = calculate_travel_time_minutes(last_job["end_loc"][0], last_job["end_loc"][1],
                                                            job["start_loc"][0], job["start_loc"][1])
                                                           
                arrival = add_minutes(last_end_time, travel)
                
                # Calculate potential shift
                diff = time_diff_minutes(arrival, original_start)
                
                if diff > 15:
                    # VIOLATION: The accumulated delay is too large (> 15m)
                    # We must BREAK the chain here.
                    # This job (job_idx) cannot be part of this bus.
                    # It must be the start of a NEW bus.
                    
                    # Add this job back to the queue to be processed as a root
                    queue.append(job_idx)
                    
                    # Stop processing this chain for the current bus
                    break
                
                if diff > 0:
                    actual_start = arrival
                
            # Calculate final shift for this item
            shift = time_diff_minutes(actual_start, original_start)
            
            actual_end = add_minutes(actual_start, duration)
            
            # Calculate deadhead (0 for first route)
            deadhead = 0
            if k > 0:
                # We calculated 'travel' above in the loop
                # But we need to access it here.
                # Let's recalculate or store it.
                # Since we are inside the loop where 'travel' was calculated:
                # Wait, 'travel' is calculated inside the 'if last_end_time:' block.
                # We can initialize travel = 0 before the block.
                pass
            
            # Actually, let's just use the 'travel' variable if it exists
            # We need to be careful about scope.
            current_deadhead = 0
            if last_end_time:
                 # Re-retrieve travel time for accuracy
                last_job_idx = chain_indices[k-1]
                curr_job_idx = job_idx
                t = travel_time_matrix[last_job_idx][curr_job_idx]
                if t is None:
                    last_job = jobs[last_job_idx]
                    t = calculate_travel_time_minutes(last_job["end_loc"][0], last_job["end_loc"][1],
                                                            job["start_loc"][0], job["start_loc"][1])
                current_deadhead = t

            final_items.append(ScheduleItem(
                route_id=job["route"].id,
                start_time=actual_start,
                end_time=actual_end,
                type=job["type"],
                original_start_time=original_start,
                time_shift_minutes=shift,
                deadhead_minutes=current_deadhead
            ))
            
            last_end_time = actual_end
            last_end_loc = job["end_loc"]
            
        if final_items:
            bus_id = f"B{len(bus_schedules)+1}"
            bus_schedules.append(BusSchedule(
                bus_id=bus_id, 
                items=final_items, 
                last_loc=None
            ))
        
    print(f"DEBUG: Generated {len(bus_schedules)} bus schedules.")
    
    # 5. Post-Optimization: Merge Morning-Only and Afternoon-Only buses
    # This addresses the issue where the optimizer might leave them separate due to large time gaps 
    # or local optima.
    print(f"DEBUG: Running post-optimization shift merging...")
    final_buses = emparejar_turnos_manana_tarde(bus_schedules)
    print(f"DEBUG: Final bus count after merging: {len(final_buses)}")

    return final_buses

def emparejar_turnos_manana_tarde(buses: List[BusSchedule], gap_minimo_minutos: int = 60) -> List[BusSchedule]:
    """
    Fusions buses that only have morning routes with buses that only have afternoon routes.
    """
    
    def get_bus_type(bus: BusSchedule) -> str:
        has_entry = any(item.type == 'entry' for item in bus.items)
        has_exit = any(item.type == 'exit' for item in bus.items)
        if has_entry and not has_exit:
            return 'morning'
        if has_exit and not has_entry:
            return 'afternoon'
        return 'mixed'

    def get_bus_end_time(bus: BusSchedule) -> time:
        # Assumes items are sorted by time (which they should be)
        return bus.items[-1].end_time

    def get_bus_start_time(bus: BusSchedule) -> time:
        return bus.items[0].start_time

    buses_solo_manana = []
    buses_solo_tarde = []
    buses_completos = []

    for bus in buses:
        b_type = get_bus_type(bus)
        if b_type == 'morning':
            buses_solo_manana.append(bus)
        elif b_type == 'afternoon':
            buses_solo_tarde.append(bus)
        else:
            buses_completos.append(bus)
            
    # Sort for optimal matching
    # Morning: ends earliest? Or latest? user said "latest end time"? 
    # Actually, to maximize compatibility with afternoon buses (which start late), 
    # a morning bus that ends LATER is HARDER to match. 
    # A morning bus that ends EARLIER is EASIER to match.
    # User pseudo code: "buses_solo_manana.sort(key=lambda b: b.hora_fin_ultima_ruta())" (Ascending by default)
    # If we process EARLIEST END first, we match them with EARLIEST START afternoon?
    # Strategy: "menor_gap".
    buses_solo_manana.sort(key=lambda b: get_bus_end_time(b))
    buses_solo_tarde.sort(key=lambda b: get_bus_start_time(b))
    
    buses_fusionados = []
    tarde_usados = set()
    
    for bus_m in buses_solo_manana:
        end_time_m = get_bus_end_time(bus_m)
        min_start_needed = add_minutes(end_time_m, gap_minimo_minutos)
        
        mejor_match = None
        
        for i, bus_t in enumerate(buses_solo_tarde):
            if i in tarde_usados:
                continue
                
            start_time_t = get_bus_start_time(bus_t)
            
            # Check feasibility: Start T >= End M + Gap
            # using time_diff checks
            # if time_diff_minutes(start_time_t, min_start_needed) >= 0:
            
            # To be safe with midnight crossing (unlikely for school bus but correct math needed):
            # Convert to minutes from midnight
            def to_mins(t): return t.hour * 60 + t.minute
            
            if to_mins(start_time_t) >= to_mins(min_start_needed):
                # Found a candidate. Since list is sorted by start time, 
                # this is the EARLIEST valid afternoon bus. 
                # This minimizes the Gap (as long as it satisfies the constraint).
                mejor_match = (i, bus_t)
                break
        
        if mejor_match:
            idx, bus_t = mejor_match
            # Merge
            # Modify bus_m to include items from bus_t
            # We should probably update the ID to reflect modification or keep bus_m's ID
            bus_m.items.extend(bus_t.items)
            # Update last_loc
            bus_m.last_loc = bus_t.last_loc
            
            buses_fusionados.append(bus_m)
            tarde_usados.add(idx)
        else:
            buses_fusionados.append(bus_m)
            
    # Add remaining afternoon buses
    for i, bus_t in enumerate(buses_solo_tarde):
        if i not in tarde_usados:
            buses_fusionados.append(bus_t)
            
    buses_fusionados.extend(buses_completos)
    
    return buses_fusionados



