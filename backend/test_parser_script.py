from backend.parser import parse_routes
import os

def test_parser():
    file_path = "mock_routes.xlsx"
    if not os.path.exists(file_path):
        print(f"File {file_path} not found.")
        return

    routes = parse_routes(file_path)
    print(f"Parsed {len(routes)} routes.")
    for r in routes:
        print(f"Route {r.id}: {r.name}, Type: {r.type}, Stops: {len(r.stops)}, Capacity: {r.capacity_needed}")
        if r.stops:
            print(f"  First Stop: {r.stops[0].name} ({r.stops[0].lat}, {r.stops[0].lon})")

if __name__ == "__main__":
    test_parser()
