# Testing Patterns

**Analysis Date:** 2026-01-19

## Test Framework

**Runner:**
- Backend: No formal test framework configured (pytest not in requirements)
- Frontend: No test framework configured (no jest/vitest in package.json)

**Current State:**
- Ad-hoc test scripts exist in `backend/` directory
- Tests are standalone Python scripts run via `python script.py`
- No automated test runner or CI integration detected

**Run Commands:**
```bash
# Backend ad-hoc tests
cd backend
python test_optimizer.py
python test_parser_script.py
python simple_merge_test.py

# Frontend (not configured)
# npm run lint  # Only linting available
```

## Test File Organization

**Location:**
- Co-located in `backend/` directory alongside production code
- No dedicated `tests/` folder

**Naming:**
- Pattern: `test_*.py` or descriptive names like `verify_*.py`, `debug_*.py`
- Examples:
  - `backend/test_optimizer.py`
  - `backend/test_parser_script.py`
  - `backend/simple_merge_test.py`
  - `backend/verify_compaction.py`
  - `backend/verify_consistency.py`

**Structure:**
```
backend/
├── models.py
├── optimizer.py
├── parser.py
├── test_optimizer.py       # Tests optimizer functions
├── test_parser_script.py   # Tests parser functions
├── simple_merge_test.py    # Integration test for merge logic
├── verify_compaction.py    # Verification script
├── verify_consistency.py   # Verification script
└── debug_*.py              # Debugging scripts
```

## Test Structure

**Suite Organization:**
```python
# Pattern: Standalone script with main block

from backend.optimizer import optimize_routes
from backend.models import Route, Stop
from datetime import time

def test_optimizer():
    # 1. Setup: Create test data
    r1 = Route(
        id="R1", name="Route 1",
        stops=[Stop(name="S1", lat=40.0, lon=-3.0, order=1, time_from_start=0)],
        school_id="SCH1", school_name="School 1",
        arrival_time=time(9, 0), capacity_needed=50,
        contract_id="C1", type="entry"
    )
    routes = [r1, r2, r3]

    # 2. Execute: Run function under test
    schedule = optimize_routes(routes)

    # 3. Output: Print results (no assertions)
    print(f"Optimized {len(routes)} routes into {len(schedule)} buses.")
    for bus in schedule:
        print(f"Bus {bus.bus_id}:")
        for item in bus.items:
            print(f"  - {item.route_id} ({item.start_time} - {item.end_time})")

if __name__ == "__main__":
    test_optimizer()
```

**Patterns:**
- Manual test data creation with Pydantic models
- Print-based output inspection (no assertions)
- Exit codes for pass/fail in some scripts (`sys.exit(1)`)

## Mocking

**Framework:** None - real dependencies used

**Patterns:**
- Tests use real OSRM API calls (cached for performance)
- No mocking of external services
- Test data is hardcoded in test scripts

**What to Mock (Recommendations):**
- OSRM API calls for offline/fast testing
- File system operations for parser tests
- Time-dependent functions

**What NOT to Mock:**
- Pydantic model validation
- Core algorithm logic

## Fixtures and Factories

**Test Data:**
```python
# Inline factory function pattern
def create_test_routes():
    r1 = Route(
        id="R_Morning",
        name="Morning Route",
        stops=[
            Stop(name="Start", lat=0, lon=0, order=1, time_from_start=0),
            Stop(name="School", lat=0.1, lon=0.1, order=2, time_from_start=30, is_school=True)
        ],
        school_id="S1",
        school_name="School 1",
        arrival_time=time(9, 0),
        capacity_needed=10,
        contract_id="C1",
        type="entry"
    )
    # ... more routes
    return [r1, r2]
```

**Location:**
- Fixtures embedded directly in test files
- No shared fixtures file
- Real Excel files used for integration tests (`mock_routes.xlsx`)

## Coverage

**Requirements:** None enforced

**Current State:**
- No coverage tooling configured
- No coverage reports generated
- Critical paths (optimizer, parser) have manual test scripts

**View Coverage:**
```bash
# Not configured - would require:
# pip install pytest-cov
# pytest --cov=backend tests/
```

## Test Types

**Unit Tests:**
- Minimal - most tests are integration-level
- `test_optimizer.py`: Tests optimizer with mock data
- `test_parser_script.py`: Tests parser with mock Excel file

**Integration Tests:**
- `simple_merge_test.py`: End-to-end optimization flow
- Tests involving OSRM API calls (network-dependent)

**E2E Tests:**
- Not implemented
- No frontend testing (Cypress, Playwright not configured)

**Verification Scripts:**
- `verify_compaction.py`: Validates fleet compaction logic
- `verify_consistency.py`: Checks schedule consistency
- `verify_parser_real.py`: Tests parser with real Excel files

## Common Patterns

**Async Testing:**
- Not applicable - all backend tests are synchronous
- Frontend has no tests

**Error Testing:**
```python
# Pattern: Check for graceful handling
def test_parser():
    file_path = "mock_routes.xlsx"
    if not os.path.exists(file_path):
        print(f"File {file_path} not found.")
        return  # Graceful exit, not an assertion

    routes = parse_routes(file_path)
    print(f"Parsed {len(routes)} routes.")
```

**Success/Failure Reporting:**
```python
# Pattern: Exit code for CI compatibility
def test_optimization():
    # ... test logic ...
    if len(schedule) == 1:
        print("SUCCESS: Routes merged into 1 bus!")
        return True
    else:
        print("FAILURE: Routes were not merged.")
        return False

if __name__ == "__main__":
    success = test_optimization()
    if not success:
        sys.exit(1)
```

## Test Data Files

**Location:**
- `mock_routes.xlsx` in project root
- Real Excel files (`UE3617 VIGO (2).xlsx`, etc.) for manual testing

**Patterns:**
- Mock data created in Python code
- Excel files for parser integration tests

## Recommendations for Improvement

**Priority Items:**

1. **Add pytest framework:**
   - Add `pytest` to `backend/requirements.txt`
   - Refactor test scripts to use `assert` statements
   - Create `backend/tests/` directory

2. **Add test coverage:**
   - Configure `pytest-cov`
   - Target critical paths: `optimizer.py`, `parser.py`

3. **Mock external services:**
   - Mock OSRM API for deterministic, fast tests
   - Use `pytest-mock` or `unittest.mock`

4. **Add frontend testing:**
   - Add Vitest to `frontend/package.json`
   - Test critical components: `FileUpload`, `DataPreviewModal`

5. **Create shared fixtures:**
   - `backend/tests/fixtures.py` with factory functions
   - Parameterized test data for edge cases

---

*Testing analysis: 2026-01-19*
