from models import Route, Stop
from optimizer import optimize_routes_lp
from datetime import time

# Create dummy routes
r1 = Route(
    id="R1",
    name="Route 1",
    arrival_time=time(9, 0),
    departure_time=None,
    capacity_needed=50,
    contract_id="C1",
    school_id="S1",
    school_name="School 1",
    type="entry",
    stops=[
        Stop(lat=40.0, lon=-3.0, name="Stop 1", order=1, time_from_start=0),
        Stop(lat=40.1, lon=-3.1, name="Stop 2", order=2, time_from_start=10)
    ]
)

r2 = Route(
    id="R2",
    name="Route 2",
    arrival_time=time(9, 30),
    departure_time=None,
    capacity_needed=50,
    contract_id="C1",
    school_id="S1",
    school_name="School 1",
    type="entry",
    stops=[
        Stop(lat=40.2, lon=-3.2, name="Stop 3", order=1, time_from_start=0),
        Stop(lat=40.3, lon=-3.3, name="Stop 4", order=2, time_from_start=10)
    ]
)

try:
    optimize_routes_lp([r1, r2])
    print("Optimization successful")
except Exception as e:
    import traceback
    traceback.print_exc()
