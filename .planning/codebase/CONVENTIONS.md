# Coding Conventions

**Analysis Date:** 2026-01-19

## Naming Patterns

**Files:**
- Python: `snake_case.py` (e.g., `router_service.py`, `pdf_service.py`)
- React components: `PascalCase.jsx` (e.g., `FileUpload.jsx`, `MapView.jsx`)
- React services: `PascalCase.js` (e.g., `RouteService.js`)
- Config files: lowercase with dots (e.g., `vite.config.js`, `tailwind.config.js`)

**Functions:**
- Python: `snake_case` (e.g., `parse_routes`, `get_real_travel_time`, `optimize_routes_lp`)
- JavaScript/React: `camelCase` (e.g., `handleOptimize`, `fetchRouteGeometry`, `uploadFiles`)
- React hooks: `use` prefix with camelCase (e.g., `useState`, `useMemo`, `useCallback`)

**Variables:**
- Python: `snake_case` for local variables, `UPPER_SNAKE_CASE` for constants
  - Constants: `OSRM_API_URL`, `MAX_TIME_SHIFT_MINUTES`, `AVERAGE_SPEED_KMH`
  - Variables: `travel_time_matrix`, `bus_schedules`, `route_info`
- JavaScript: `camelCase` (e.g., `mapData`, `selectedBus`, `busColors`)

**Types/Classes:**
- Python: `PascalCase` using Pydantic BaseModel
  - Examples: `Route`, `Stop`, `Bus`, `BusSchedule`, `ScheduleItem`
- React components: `PascalCase` (e.g., `FileUpload`, `DataPreviewModal`)

**Route/Endpoint naming:**
- API endpoints: lowercase with underscores (e.g., `/upload`, `/optimize`, `/optimize_lp`, `/export_pdf`)

## Code Style

**Formatting:**
- Python: Standard PEP 8 style (no explicit formatter config detected)
- JavaScript/React: 4-space indentation
- Line length: No explicit limit enforced

**Linting:**
- Frontend: ESLint with React plugins
  - `eslint-plugin-react`
  - `eslint-plugin-react-hooks`
  - `eslint-plugin-react-refresh`
- Backend: No explicit linting config (relies on IDE defaults)

## Import Organization

**Python Backend Order:**
1. Standard library imports (`math`, `logging`, `datetime`, `typing`, `io`, `os`, `json`)
2. Third-party imports (`pandas`, `requests`, `pydantic`, `fastapi`, `reportlab`)
3. Local imports (`from models import Route, Stop`, `from parser import parse_routes`)

**JavaScript/React Order:**
1. React imports (`import React, { useState, useMemo } from 'react'`)
2. Third-party libraries (`import L from 'leaflet'`, `import { MapContainer } from 'react-leaflet'`)
3. Local components (`import FileUpload from './components/FileUpload'`)
4. Local services (`import { fetchRouteGeometry } from '../services/RouteService'`)
5. Styles (`import 'leaflet/dist/leaflet.css'`)

**Path Aliases:**
- None configured - relative paths used throughout
- Frontend uses `./` and `../` relative imports

## Error Handling

**Python Patterns:**
```python
# Try-except with specific exception types
try:
    with pd.ExcelFile(file_path) as xls:
        # ... parsing logic
except Exception as e:
    logger.error(f"Error parsing Excel file: {e}")
    import traceback
    traceback.print_exc()
    return []

# API error handling with HTTPException
try:
    # operation
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))

# Graceful degradation with fallbacks
osrm_time = get_real_travel_time(lat1, lon1, lat2, lon2)
if osrm_time is not None:
    return osrm_time
# Fallback to Haversine calculation
```

**JavaScript/React Patterns:**
```javascript
// Async/await with try-catch
try {
    const response = await fetch(url, options);
    if (!response.ok) throw new Error('Request failed');
    const data = await response.json();
    onUploadSuccess(data);
} catch (err) {
    setError(err.message);
} finally {
    setUploading(false);
}

// Console error logging for non-blocking failures
catch (error) {
    console.error("Error fetching route geometry:", error);
    return stops.map(s => [s.lat, s.lon]); // Fallback
}
```

## Logging

**Framework:** Python `logging` module for backend

**Patterns:**
```python
logger = logging.getLogger(__name__)

# Debug level for verbose info
logger.debug(f"Loaded {len(_travel_time_cache)} entries from OSRM cache.")
logger.debug(f"Expedition columns - route: {route_code_col}, sentido: {sentido_col}")

# Info level for summary info
logger.info(f"Parsed {len(routes)} unique routes: {entry_count} entry, {exit_count} exit")
logger.info("PHASE 3: ELIMINATING UNDERUTILIZED BUSES")

# Warning level for recoverable issues
logger.warning(f"Skipping route {route.id} (entry) due to missing arrival time")
logger.warning(f"{len(routes_without_time)} routes have no time info")

# Error level for failures
logger.error(f"Error parsing Excel file: {e}")
```

**Frontend:** Uses `console.log`, `console.error` for debugging

## Comments

**When to Comment:**
- Module/file-level docstrings explaining purpose
- Complex algorithm sections with step-by-step explanations
- Configuration constants with their meaning
- Non-obvious business logic

**Docstring Pattern (Python):**
```python
def optimize_routes_lp(routes: List[Route]) -> List[BusSchedule]:
    """
    Optimizes fleet size using a Minimum Path Cover on a DAG.
    Includes OSRM real travel times and +/- 15 min time windows.
    """

def get_travel_time_matrix(sources, destinations) -> List[List[Optional[int]]]:
    """
    Fetch travel time matrix for multiple sources and destinations.
    Handles chunking to respect OSRM limits (100 coords per request).
    Returns a 2D list where result[i][j] is time from sources[i] to destinations[j].
    """
```

**JSDoc Pattern (JavaScript):**
```javascript
/**
 * Fetches the route geometry (polyline) for a given set of stops.
 * @param {Array<{lat: number, lon: number}>} stops - List of stops (lat, lon).
 * @returns {Promise<Array<[number, number]>>} - List of [lat, lon] points for the polyline.
 */
```

**Inline Comments:**
- Section separators: `# ============================================================`
- Step markers: `# 1. Convert all routes to "Jobs"`
- Configuration explanations: `# Maximum allowed shift from original schedule`

## Function Design

**Size:**
- Backend functions range from small helpers (5-10 lines) to complex algorithms (100+ lines)
- No strict limit, but complex functions are broken into logical sections with comments

**Parameters:**
- Python: Type hints used consistently (`def parse_routes(file_path: str) -> List[Route]`)
- Default parameters for optional config (`def compact_fleet(buses, max_passes: int = COMPACT_MAX_PASSES)`)
- JavaScript: Destructuring for component props (`const FileUpload = ({ onUploadSuccess })`)

**Return Values:**
- Python: Explicit return types via type hints
- Return empty list `[]` on error rather than `None` for collections
- Return `Optional[T]` when value may not exist
- JavaScript: Implicit returns avoided; explicit returns preferred

## Module Design

**Exports:**
- Python: No `__all__` defined; implicit exports
- JavaScript: Named exports for services (`export const fetchRouteGeometry`)
- React: Default exports for components (`export default FileUpload`)

**Barrel Files:**
- Not used in this codebase

**Module Responsibility:**
- `backend/models.py`: Pydantic data models only
- `backend/parser.py`: Excel file parsing logic
- `backend/optimizer.py`: Route optimization algorithms
- `backend/router_service.py`: OSRM API integration
- `backend/pdf_service.py`: PDF report generation
- `backend/main.py`: FastAPI app and endpoint definitions
- `frontend/src/services/`: API communication utilities

## Data Models

**Pattern:** Pydantic BaseModel with type hints

```python
class Stop(BaseModel):
    name: str
    lat: float
    lon: float
    order: int
    time_from_start: int  # minutes
    passengers: int = 0
    is_school: bool = False

class Route(BaseModel):
    id: str
    name: str
    stops: List[Stop]
    school_id: str
    school_name: str
    arrival_time: Optional[time] = None
    departure_time: Optional[time] = None
    capacity_needed: int
    contract_id: str
    type: str  # "entry" or "exit"
```

**Conventions:**
- Use `Optional[T]` for nullable fields with `= None` default
- Add comments for non-obvious field units (e.g., `# minutes`)
- Keep models flat; nested models use composition

## React Component Patterns

**State Management:**
- Local state with `useState` hooks
- No global state library (Redux/Zustand) - state lifted to `App.jsx`
- Derived state with `useMemo` for computed values

**Component Structure:**
```javascript
const ComponentName = ({ prop1, prop2 }) => {
    // State declarations
    const [state, setState] = useState(initial);

    // Memoized values
    const derived = useMemo(() => compute(data), [data]);

    // Effects
    useEffect(() => { /* side effects */ }, [deps]);

    // Event handlers
    const handleAction = async () => { /* logic */ };

    // Render
    return (
        <div className="...">
            {/* JSX */}
        </div>
    );
};

export default ComponentName;
```

**Styling:**
- Tailwind CSS utility classes inline
- Color scheme: Slate-900 dark theme with indigo/emerald/amber accents
- Consistent spacing and rounding patterns

---

*Convention analysis: 2026-01-19*
