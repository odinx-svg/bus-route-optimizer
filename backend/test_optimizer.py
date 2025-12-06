from backend.optimizer import optimize_routes
from backend.models import Route, Stop
from datetime import time

def test_optimizer():
    # Create dummy routes
    r1 = Route(
        id="R1", name="Route 1", stops=[Stop(name="S1", lat=40.0, lon=-3.0, order=1, time_from_start=0)],
        school_id="SCH1", school_name="School 1", arrival_time=time(9, 0), capacity_needed=50, contract_id="C1", type="entry"
    )
    
    # R2 starts earlier, finishes at 8:30. Bus from R2 might do R1?
    # R2 arrival 8:30. R1 start 8:30 (assuming 30 min duration).
    # If distance is 0, it matches.
    
    r2 = Route(
        id="R2", name="Route 2", stops=[Stop(name="S2", lat=40.0, lon=-3.0, order=1, time_from_start=0)],
        school_id="SCH1", school_name="School 1", arrival_time=time(8, 30), capacity_needed=50, contract_id="C1", type="entry"
    )
    
    # R3 Exit route. Departs 14:00.
    r3 = Route(
        id="R3", name="Route 3", stops=[Stop(name="S1", lat=40.0, lon=-3.0, order=1, time_from_start=0)], # School
        school_id="SCH1", school_name="School 1", arrival_time=time(14, 0), departure_time=time(14, 0), capacity_needed=50, contract_id="C1", type="exit"
    )
    
    routes = [r1, r2, r3]
    schedule = optimize_routes(routes)
    
    print(f"Optimized {len(routes)} routes into {len(schedule)} buses.")
    for bus in schedule:
        print(f"Bus {bus.bus_id}:")
        for item in bus.items:
            print(f"  - {item.route_id} ({item.start_time} - {item.end_time})")

if __name__ == "__main__":
    test_optimizer()
