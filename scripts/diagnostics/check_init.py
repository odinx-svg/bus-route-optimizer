data = open('backend/config/__init__.py', 'rb').read()
print(f'Size: {len(data)}')
null_byte = b'\x00'
print(f'Nulls: {data.count(null_byte)}')
