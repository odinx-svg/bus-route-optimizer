from parser import parse_routes
import os

file_path = "../mock_routes.xlsx"
if not os.path.exists(file_path):
    print("File not found")
else:
    print(f"Parsing {file_path}")
    routes = parse_routes(file_path)
    print(f"Routes found: {len(routes)}")
