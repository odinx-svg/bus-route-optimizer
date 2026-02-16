import os

for root, dirs, files in os.walk('backend'):
    for f in files:
        if f == '__init__.py':
            path = os.path.join(root, f)
            with open(path, 'rb') as file:
                data = file.read()
            nulls = data.count(b'\x00')
            if nulls > 0:
                print(f"CORRUPT: {path} ({nulls} nulls)")
            else:
                print(f"OK: {path}")
