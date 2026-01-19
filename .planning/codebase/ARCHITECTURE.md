# Architecture

**Analysis Date:** 2026-01-19

## Pattern Overview

**Overall:** Client-Server Monolith with Service-Oriented Backend

**Key Characteristics:**
- Decoupled React frontend communicating with Python FastAPI backend via REST
- Backend follows a pipeline pattern: Parse -> Optimize -> Export
- External OSRM API integration for real-world routing data
- Stateless request handling (no database, file-based data input)
- Linear Programming optimization core using PuLP solver

## Layers

**Presentation Layer (Frontend):**
- Purpose: User interface for file upload, optimization control, and results visualization
- Location: `frontend/src/`
- Contains: React components, services, Leaflet map integration
- Depends on: Backend REST API, OSRM API (client-side for route geometry)
- Used by: End users via browser

**API Layer (Backend Entry Point):**
- Purpose: HTTP request handling, routing, validation, response formatting
- Location: `backend/main.py`
- Contains: FastAPI app, endpoint definitions, CORS middleware, file handling
- Depends on: Parser, Optimizer, PDF Service
- Used by: Frontend via HTTP

**Domain Services Layer:**
- Purpose: Core business logic for parsing, optimization, and export
- Location: `backend/parser.py`, `backend/optimizer.py`, `backend/pdf_service.py`
- Contains: Route parsing, fleet optimization algorithms, PDF generation
- Depends on: Models, Router Service
- Used by: API Layer

**External Integration Layer:**
- Purpose: Communication with external OSRM routing service
- Location: `backend/router_service.py`
- Contains: OSRM API calls, caching, travel time matrix computation
- Depends on: OSRM public API (https://router.project-osrm.org)
- Used by: Optimizer

**Data Models Layer:**
- Purpose: Pydantic data structures for type safety and validation
- Location: `backend/models.py`
- Contains: Stop, Route, Bus, ScheduleItem, BusSchedule models
- Depends on: Pydantic
- Used by: All backend layers

## Data Flow

**Upload and Parse Flow:**

1. User uploads Excel files (.xlsx) via FileUpload component
2. Frontend sends multipart POST to `/upload` endpoint
3. Backend saves temp files, parses via `parser.parse_routes()`
4. Parser reads sheets (Rutas, Paradas, Expedicions), builds Route objects
5. Returns List[Route] as JSON to frontend
6. Frontend shows DataPreviewModal for user verification

**Optimization Flow:**

1. User clicks "Run Optimization" after data preview
2. Frontend POSTs routes JSON to `/optimize_lp` endpoint
3. Optimizer prepares jobs from routes (entry/exit with times)
4. Router service fetches travel time matrix from OSRM
5. PuLP solver finds minimum path cover (maximum matching)
6. Post-processing: morning/afternoon merge, fleet compaction, underutilized elimination
7. Returns List[BusSchedule] as JSON
8. Frontend displays MapView with schedule visualization

**Export Flow:**

1. User clicks "Export PDF" in results view
2. Frontend POSTs schedule JSON to `/export_pdf` endpoint
3. PDF service generates PDF using ReportLab
4. Returns PDF as StreamingResponse for download

**State Management:**
- Frontend: React useState hooks for routes, schedule, UI state
- Backend: Stateless per request; OSRM cache persisted to `osrm_cache.json`
- No database; all data from uploaded Excel files

## Key Abstractions

**Route:**
- Purpose: Represents a single bus route (entry or exit type)
- Examples: `backend/models.py:Route`
- Pattern: Pydantic BaseModel with validation
- Contains: id, name, stops, school info, times, capacity, type

**BusSchedule:**
- Purpose: Represents a bus's daily schedule (list of route assignments)
- Examples: `backend/models.py:BusSchedule`
- Pattern: Pydantic BaseModel
- Contains: bus_id, items (List[ScheduleItem]), last_loc

**ScheduleItem:**
- Purpose: Single route assignment within a bus schedule
- Examples: `backend/models.py:ScheduleItem`
- Pattern: Pydantic BaseModel
- Contains: route_id, times, type, time_shift, deadhead, stops

**Stop:**
- Purpose: Geographic point with timing and passenger info
- Examples: `backend/models.py:Stop`
- Pattern: Pydantic BaseModel
- Contains: name, lat, lon, order, time_from_start, passengers

## Entry Points

**Backend API Server:**
- Location: `backend/main.py`
- Triggers: `uvicorn main:app --reload` (dev), direct Python run
- Responsibilities: Initialize FastAPI, register routes, handle requests
- Endpoints:
  - `GET /` - Health check
  - `POST /upload` - Parse Excel files
  - `POST /optimize` - Greedy optimization (legacy)
  - `POST /optimize_lp` - LP-based optimization (primary)
  - `POST /export_pdf` - Generate PDF schedule

**Frontend Application:**
- Location: `frontend/src/main.jsx`
- Triggers: `npm run dev` (Vite dev server)
- Responsibilities: Mount React app to DOM

**Startup Script:**
- Location: `start_tutti.bat`
- Triggers: Double-click on Windows
- Responsibilities: Start both backend and frontend servers

## Error Handling

**Strategy:** Try-except with HTTP exceptions

**Patterns:**
- API endpoints wrap operations in try-except, return HTTPException on failure
- Parser catches Excel parsing errors, returns empty list with logging
- Router service returns None on OSRM failures, triggering Haversine fallback
- Frontend shows alert() on API errors

## Cross-Cutting Concerns

**Logging:** Python logging module configured per-module (logger = logging.getLogger(__name__))

**Validation:** Pydantic models validate request/response data automatically

**Authentication:** None (local-only application)

**Caching:** OSRM travel times cached to `osrm_cache.json` with JSON serialization

**Configuration:** Environment variables for OSRM URLs (OSRM_URL, OSRM_TABLE_URL), hardcoded defaults

---

*Architecture analysis: 2026-01-19*
