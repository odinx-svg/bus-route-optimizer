# Codebase Structure

**Analysis Date:** 2026-01-19

## Directory Layout

```
bus-route-optimizer/
├── backend/                    # Python FastAPI backend
│   ├── main.py                 # API entry point
│   ├── models.py               # Pydantic data models
│   ├── parser.py               # Excel file parser
│   ├── optimizer.py            # Fleet optimization algorithms
│   ├── router_service.py       # OSRM API integration
│   ├── pdf_service.py          # PDF generation
│   ├── requirements.txt        # Python dependencies
│   ├── osrm_cache.json         # Cached OSRM responses
│   └── [debug/test scripts]    # Various test and debug utilities
├── frontend/                   # React Vite frontend
│   ├── src/
│   │   ├── main.jsx            # React entry point
│   │   ├── App.jsx             # Main application component
│   │   ├── index.css           # Global styles (Tailwind)
│   │   ├── components/         # React components
│   │   └── services/           # API/external service calls
│   ├── package.json            # NPM dependencies
│   ├── vite.config.js          # Vite configuration
│   ├── tailwind.config.js      # Tailwind CSS config
│   └── postcss.config.js       # PostCSS config
├── .venv/                      # Python virtual environment
├── .planning/                  # Planning documentation
│   └── codebase/               # Codebase analysis docs
├── start_tutti.bat             # Windows startup script
├── mock_routes.xlsx            # Sample test data
└── [*.xlsx, *.pdf]             # User data files (not committed)
```

## Directory Purposes

**backend/:**
- Purpose: All Python server-side code
- Contains: API, business logic, external integrations, data models
- Key files:
  - `main.py`: FastAPI application and route handlers
  - `models.py`: Pydantic schemas (Stop, Route, Bus, ScheduleItem, BusSchedule)
  - `parser.py`: Excel parsing with pandas
  - `optimizer.py`: Fleet optimization (greedy + LP algorithms)
  - `router_service.py`: OSRM travel time API wrapper
  - `pdf_service.py`: ReportLab PDF generation

**frontend/src/:**
- Purpose: React application source code
- Contains: Components, services, entry point
- Key files:
  - `main.jsx`: React DOM mounting
  - `App.jsx`: Main app with state management and routing logic
  - `index.css`: Tailwind base imports

**frontend/src/components/:**
- Purpose: Reusable React UI components
- Contains: All visual components
- Key files:
  - `FileUpload.jsx`: Drag-and-drop Excel file upload
  - `MapView.jsx`: Leaflet map with route visualization and fleet sidebar
  - `DataPreviewModal.jsx`: Preview parsed routes before optimization

**frontend/src/services/:**
- Purpose: External API communication utilities
- Contains: OSRM client-side integration
- Key files:
  - `RouteService.js`: Fetch route geometry from OSRM for map display

## Key File Locations

**Entry Points:**
- `backend/main.py`: FastAPI server entry
- `frontend/src/main.jsx`: React app entry
- `start_tutti.bat`: Combined startup script

**Configuration:**
- `backend/requirements.txt`: Python packages
- `frontend/package.json`: NPM packages
- `frontend/vite.config.js`: Build configuration
- `frontend/tailwind.config.js`: CSS framework config

**Core Logic:**
- `backend/optimizer.py`: Fleet optimization algorithms (~1077 lines)
- `backend/parser.py`: Excel parsing logic (~369 lines)
- `backend/router_service.py`: OSRM integration (~204 lines)

**Testing:**
- `backend/test_optimizer.py`: Optimizer unit tests
- `backend/test_parser_script.py`: Parser tests
- `backend/test_*.py`: Various test scripts (not organized in test directory)

**Data Models:**
- `backend/models.py`: All Pydantic schemas

## Naming Conventions

**Files:**
- Python: snake_case.py (e.g., `router_service.py`, `pdf_service.py`)
- React components: PascalCase.jsx (e.g., `FileUpload.jsx`, `MapView.jsx`)
- React services: PascalCase.js (e.g., `RouteService.js`)
- Config files: lowercase with dots (e.g., `vite.config.js`, `tailwind.config.js`)

**Directories:**
- All lowercase (e.g., `backend/`, `frontend/`, `components/`, `services/`)

**Functions:**
- Python: snake_case (e.g., `parse_routes`, `optimize_routes_lp`)
- JavaScript: camelCase (e.g., `handleUploadSuccess`, `fetchRouteGeometry`)

**Components:**
- PascalCase (e.g., `FileUpload`, `MapView`, `DataPreviewModal`)

**Variables:**
- Python: snake_case (e.g., `travel_time_matrix`, `bus_schedules`)
- JavaScript: camelCase (e.g., `selectedBus`, `mapData`)

## Where to Add New Code

**New API Endpoint:**
- Add route handler in `backend/main.py`
- Add service function in appropriate service file or create new one
- Add models in `backend/models.py` if needed

**New Business Logic:**
- Parser changes: `backend/parser.py`
- Optimization changes: `backend/optimizer.py`
- New external integration: Create `backend/<service>_service.py`

**New React Component:**
- Create file in `frontend/src/components/<ComponentName>.jsx`
- Import and use in `frontend/src/App.jsx` or parent component

**New Frontend Service:**
- Create file in `frontend/src/services/<ServiceName>.js`
- Export functions for API calls

**New Data Model:**
- Add Pydantic class to `backend/models.py`
- Frontend TypeScript types would go in `frontend/src/types/` (not yet created)

**Utilities:**
- Backend: Create `backend/utils.py` (not yet exists)
- Frontend: Create `frontend/src/utils/` directory (not yet exists)

**Tests:**
- Backend: Add `backend/test_<module>.py` (flat structure currently)
- Consider organizing into `backend/tests/` directory

## Special Directories

**.venv/:**
- Purpose: Python virtual environment
- Generated: Yes (by python -m venv)
- Committed: No (.gitignore)

**frontend/node_modules/:**
- Purpose: NPM dependencies
- Generated: Yes (by npm install)
- Committed: No (.gitignore)

**backend/__pycache__/:**
- Purpose: Python bytecode cache
- Generated: Yes (by Python interpreter)
- Committed: No

**.planning/:**
- Purpose: Project planning and documentation
- Generated: No (manual)
- Committed: Yes

**.claude/:**
- Purpose: Claude Code configuration
- Generated: No (manual)
- Committed: Yes

---

*Structure analysis: 2026-01-19*
