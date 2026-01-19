
from datetime import time
from models import Route, Stop
from optimizer import optimize_routes_lp, optimize_routes
import sys

# Mock Data
def create_test_routes():
    # Morning Route: 08:00 - 09:00
    r1 = Route(
        id="R_Morning",
        name="Morning Route",
        stops=[
            Stop(name="Start", lat=0, lon=0, order=1, time_from_start=0),
            Stop(name="School", lat=0.1, lon=0.1, order=2, time_from_start=30, is_school=True)
        ],
        school_id="S1",
        school_name="School 1",
        arrival_time=time(9, 0), # Arrives at school at 9:00
        capacity_needed=10,
        contract_id="C1",
        type="entry"
    )

    # Afternoon Route: 14:00 - 15:00
    r2 = Route(
        id="R_Afternoon",
        name="Afternoon Route",
        stops=[
            Stop(name="School", lat=0.1, lon=0.1, order=1, time_from_start=0, is_school=True),
            Stop(name="End", lat=0, lon=0, order=2, time_from_start=30)
        ],
        school_id="S1",
        school_name="School 1",
        departure_time=time(14, 0), # Leaves school at 14:00
        capacity_needed=10,
        contract_id="C1",
        type="exit"
    )
    
    return [r1, r2]

def test_optimization():
    print("--- Testing Optimization (Expecting Merge) ---")
    routes = create_test_routes()
    
    # Run LP Optimizer
    print("Running optimize_routes_lp...")
    try:
        schedule = optimize_routes_lp(routes)
    except ImportError:
        print("Pulp not installed, falling back to basic optimize_routes")
        schedule = optimize_routes(routes)
        
    print(f"Result: {len(schedule)} buses used.")
    
    for bus in schedule:
        print(f"Bus {bus.bus_id}:")
        for item in bus.items:
            print(f"  - {item.type.upper()} {item.route_id} ({item.start_time} -> {item.end_time})")
            
    if len(schedule) == 1:
        print("SUCCESS: Routes merged into 1 bus!")
        return True
    else:
        print("FAILURE: Routes were not merged.")
        return False

if __name__ == "__main__":
    success = test_optimization()
    if not success:
        sys.exit(1)
