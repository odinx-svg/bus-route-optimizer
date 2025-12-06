import sys
import os
from parser import parse_routes
from optimizer import optimize_routes_lp
from models import Route

def verify():
    # Load mock data
    file_path = "../mock_routes.xlsx"
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return

    print("Loading routes...")
    routes = parse_routes(file_path)
    print(f"Loaded {len(routes)} routes.")

    # Run optimization
    print("Running Weighted Optimization...")
    try:
        schedule = optimize_routes_lp(routes)
    except Exception as e:
        print(f"Optimization failed: {e}")
        import traceback
        traceback.print_exc()
        return

    print(f"Optimization complete. Generated {len(schedule)} buses.")

    total_deadhead = 0
    total_routes = 0

    for bus in schedule:
        print(f"\nBus {bus.bus_id}: {len(bus.items)} routes")
        for item in bus.items:
            total_routes += 1
            total_deadhead += item.deadhead_minutes
            print(f"  - Route {item.route_id} ({item.type}): {item.start_time} -> {item.end_time} (Deadhead: {item.deadhead_minutes}m, Shift: {item.time_shift_minutes}m)")

    print("\n--- Metrics ---")
    print(f"Total Buses: {len(schedule)}")
    print(f"Total Routes: {total_routes}")
    print(f"Total Deadhead: {total_deadhead} min")
    if len(schedule) > 0:
        print(f"Avg Routes/Bus: {total_routes/len(schedule):.2f}")
    else:
        print("Avg Routes/Bus: 0.00")

if __name__ == "__main__":
    verify()
