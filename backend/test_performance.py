import time
from models import Route, Stop
from optimizer import optimize_routes_lp
from datetime import time as dt_time
import random

def create_mock_routes(n=20):
    routes = []
    for i in range(n):
        # Create routes spread out geographically to trigger OSRM calls (or filtering)
        # Increase spacing to 0.1 degrees (~11km) to trigger filter more often
        lat_base = 40.0 + (i * 0.1) 
        lon_base = -3.0 + (i * 0.1)
        
        r = Route(
            id=f"R{i}",
            name=f"Route {i}",
            arrival_time=dt_time(9, 0),
            departure_time=None,
            capacity_needed=50,
            contract_id="C1",
            school_id="S1",
            school_name="School 1",
            type="entry",
            stops=[
                Stop(lat=lat_base, lon=lon_base, name=f"Stop 1", order=1, time_from_start=0),
                Stop(lat=lat_base+0.005, lon=lon_base+0.005, name=f"Stop 2", order=2, time_from_start=10)
            ]
        )
        routes.append(r)
    return routes

if __name__ == "__main__":
    print("Generating mock routes...")
    print("Generating mock routes...")
    routes = create_mock_routes(60)
    
    print("Starting optimization...")
    start_time = time.time()
    
    try:
        schedule = optimize_routes_lp(routes)
        end_time = time.time()
        print(f"Optimization finished in {end_time - start_time:.2f} seconds")
        print(f"Generated {len(schedule)} bus schedules")
    except Exception as e:
        print(f"Optimization FAILED: {e}")
        import traceback
        traceback.print_exc()
