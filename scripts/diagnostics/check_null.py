import os

for path in [
    'backend/config/osrm.py',
    'backend/test_import.py'
]:
    if os.path.exists(path):
        with open(path, 'rb') as f:
            data = f.read()
        nulls = data.count(b'\x00')
        print(f"{path}: {len(data)} bytes, {nulls} null bytes")
        if nulls > 0:
            # Find first null
            pos = data.find(b'\x00')
            print(f"  First null at position {pos}")
            print(f"  Context: {data[max(0,pos-10):pos+10]}")
    else:
        print(f"{path}: NOT FOUND")
