import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from optimizer import optimize_routes_lp
from models import Route, Stop
from datetime import time

# Mock Data Creation
def create_mock_routes(num_routes=20):
    routes = []
    for i in range(num_routes):
        # Create a mix of entry and exit routes
        r_type = "entry" if i % 2 == 0 else "exit"
        
        # Stagger times to allow chaining
        # Entry: 8:00, 8:30, 9:00...
        # Exit: 14:00, 14:30, 15:00...
        
        if r_type == "entry":
            arrival = time(8 + (i % 3), (i % 2) * 30) # 8:00, 8:30, 9:00, 9:30...
            departure = None
        else:
            arrival = None
            departure = time(14 + (i % 3), (i % 2) * 30) # 14:00, 14:30...

        # Stops close to each other to allow chaining
        stops = [
            Stop(name="Stop A", lat=42.0 + (i*0.01), lon=-8.0, order=1, time_from_start=0),
            Stop(name="Stop B", lat=42.05 + (i*0.01), lon=-8.05, order=2, time_from_start=10)
        ]

        routes.append(Route(
            id=f"R{i}",
            name=f"Route {i}",
            school_name="School",
            school_id="S1",
            contract_id=f"C{i}",
            stops=stops,
            arrival_time=arrival,
            departure_time=departure,
            capacity_needed=10,
            type=r_type
        ))
    return routes

if __name__ == "__main__":
    print("Generating mock routes...")
    routes = create_mock_routes(50) # Create 50 routes
    
    print(f"Optimizing {len(routes)} routes...")
    try:
        schedule = optimize_routes_lp(routes)
        
        num_buses = len(schedule)
        avg_routes = len(routes) / num_buses if num_buses > 0 else 0
        
        print("-" * 30)
        print(f"Total Routes: {len(routes)}")
        print(f"Total Buses: {num_buses}")
        print(f"Average Routes/Bus: {avg_routes:.2f}")
        print("-" * 30)
        
        if avg_routes >= 5:
            print("SUCCESS: Target of 5 routes/bus reached or exceeded.")
        else:
            print("WARNING: Target of 5 routes/bus NOT reached. Try relaxing constraints further.")
            
    except Exception as e:
        print(f"Optimization failed: {e}")
