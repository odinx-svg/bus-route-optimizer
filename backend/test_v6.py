"""Test script to compare V5 vs V6 optimizer on real data."""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

from parser import parse_routes

# Parse all Excel files
files = [
    r'C:\Users\Juanjo\Desktop\ODINX LABS\UE3617 VIGO (2).xlsx',
    r'C:\Users\Juanjo\Desktop\ODINX LABS\UE3618 VIGO (1).xlsx',
    r'C:\Users\Juanjo\Desktop\ODINX LABS\UE3619 VIGO (1).xlsx',
    r'C:\Users\Juanjo\Desktop\ODINX LABS\UE3620 VIGO (1).xlsx',
    r'C:\Users\Juanjo\Desktop\ODINX LABS\UE3622 VIGO (1).xlsx',
]

print("=" * 60)
print("PARSING INPUT FILES")
print("=" * 60)

all_routes = []
for f in files:
    routes = parse_routes(f)
    print(f"  {os.path.basename(f)}: {len(routes)} routes")
    all_routes.extend(routes)

print(f"\nTotal routes: {len(all_routes)}")
entries = sum(1 for r in all_routes if r.type == "entry")
exits = sum(1 for r in all_routes if r.type == "exit")
print(f"  Entries: {entries}, Exits: {exits}")

# Test V5
print("\n" + "=" * 60)
print("RUNNING V5 OPTIMIZER")
print("=" * 60)
from optimizer_v5 import optimize_v5
start = time.time()
v5_result = optimize_v5(all_routes)
v5_time = time.time() - start
v5_buses = len(v5_result)
v5_routes = sum(len(b.items) for b in v5_result)
print(f"\nV5: {v5_buses} buses, {v5_routes} routes in {v5_time:.1f}s")

# Test V6
print("\n" + "=" * 60)
print("RUNNING V6 OPTIMIZER")
print("=" * 60)
from optimizer_v6 import optimize_v6
start = time.time()
v6_result = optimize_v6(all_routes)
v6_time = time.time() - start
v6_buses = len(v6_result)
v6_routes = sum(len(b.items) for b in v6_result)
print(f"\nV6: {v6_buses} buses, {v6_routes} routes in {v6_time:.1f}s")

# Comparison
print("\n" + "=" * 60)
print("COMPARISON")
print("=" * 60)
print(f"  V5: {v5_buses} buses ({v5_routes} routes) in {v5_time:.1f}s")
print(f"  V6: {v6_buses} buses ({v6_routes} routes) in {v6_time:.1f}s")
diff = v5_buses - v6_buses
if diff > 0:
    print(f"  V6 saves {diff} buses ({diff/v5_buses*100:.1f}% reduction)")
elif diff < 0:
    print(f"  V5 is better by {-diff} buses")
else:
    print(f"  Same bus count")

# Verify all routes assigned
v6_route_ids = set()
for bus in v6_result:
    for item in bus.items:
        v6_route_ids.add(item.route_id)

input_route_ids = set(r.id for r in all_routes)
missing = input_route_ids - v6_route_ids
if missing:
    print(f"\n  WARNING: {len(missing)} routes not assigned in V6!")
    for rid in list(missing)[:5]:
        print(f"    - {rid}")
else:
    print(f"\n  All {len(input_route_ids)} routes assigned in V6")
