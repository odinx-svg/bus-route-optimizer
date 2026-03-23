# Dirty Data Cases

## Cases already handled in `backend/parser.py`

- Column names with accents, casing or extra spaces.
- Empty tokens: `nan`, `none`, `null`, `nat`, `<na>`.
- Times as:
  - `datetime.time`
  - `datetime.datetime`
  - strings like `08:30`, `08:30:00`, `08.30`
  - numeric values like `8`, `8.5`
- Durations as:
  - `timedelta`
  - `HH:MM:SS`
  - numeric minutes
- Capacity ranges like:
  - `26-38`
  - `39 - 55`
  - `26/38`
  - `> 55`

## Structural variability

- Multiple sheets with similar names.
- Parenthesized suffixes such as `(2)`.
- Missing stops sheet or expeditions sheet.
- Route metadata split across different tabs.

## Safe parser checklist

- Search before editing:
  - `parse_time_value`
  - `parse_duration_to_minutes`
  - `parse_vehicle_capacity_range`
  - `find_column`
  - `parse_routes_with_report`
- Re-run:
  - `backend/tests/test_parser.py`
  - any benchmark or sample workbook flow that uses real Excel files

## Anti-patterns

- Replacing pattern-based matching with exact headers.
- Converting warnings into hard failures without evidence.
- Removing fallback routes generation because it looks redundant.
- Assuming all invalid rows should crash the import.

