# External Integrations

**Analysis Date:** 2025-01-19

## APIs & External Services

**Routing & Navigation:**
- **OSRM (Open Source Routing Machine)** - Real-time driving directions and travel time calculations
  - Public API: `https://router.project-osrm.org`
  - Endpoints used:
    - `/route/v1/driving/{coords}` - Single route with geometry
    - `/table/v1/driving/{coords}` - Travel time matrix
  - SDK/Client: Raw `requests` HTTP calls (`backend/router_service.py`)
  - Auth: None (public API, no key required)
  - Rate limiting: Implicit (public API fair use)
  - Fallback: Haversine distance calculation with configurable speed (45 km/h default)

**Map Tiles:**
- **OpenStreetMap** - Map tile rendering via Leaflet default tile layer
  - No explicit configuration (Leaflet defaults)
  - Usage: Frontend map visualization (`frontend/src/components/MapView.jsx`)

## Data Storage

**Databases:**
- None - No database integration
- All data is file-based (uploaded Excel files, JSON cache)

**File Storage:**
- Local filesystem only
- Uploaded files: Temporary storage in `backend/temp_{filename}`, deleted after parsing
- Cache: `osrm_cache.json` at project root (persistent travel time cache)

**Caching:**
- Custom JSON file cache for OSRM responses
  - Location: `osrm_cache.json` (project root) and `backend/osrm_cache.json`
  - Cache key format: `{lat1},{lon1}|{lat2},{lon2}` (rounded to 5 decimals)
  - Persisted on every cache update
  - Loaded on module import (`backend/router_service.py`)

## Authentication & Identity

**Auth Provider:**
- None - No authentication implemented
- CORS: Fully open (`allow_origins=["*"]`) - configured in `backend/main.py`

## Monitoring & Observability

**Error Tracking:**
- None - No external error tracking service

**Logs:**
- Python `logging` module (console output only)
- Log level: DEBUG for detailed optimization logging
- Key loggers:
  - `backend/optimizer.py` - Optimization progress and validation
  - `backend/router_service.py` - OSRM API calls
  - `backend/parser.py` - Excel parsing progress

## CI/CD & Deployment

**Hosting:**
- Local development only (no deployment configuration detected)
- Development servers:
  - Backend: `localhost:8000` (uvicorn)
  - Frontend: `localhost:5173` (Vite)

**CI Pipeline:**
- None - No CI/CD configuration files detected

## Environment Configuration

**Required env vars:**
- None strictly required (defaults available for all)

**Optional env vars:**
- `OSRM_URL` - Override OSRM routing endpoint
- `OSRM_TABLE_URL` - Override OSRM table endpoint

**Secrets location:**
- No secrets required (uses public APIs only)

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## API Endpoints (Internal)

**Backend REST API (`backend/main.py`):**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Health check, returns welcome message |
| `/upload` | POST | Upload Excel files, returns parsed routes |
| `/optimize` | POST | Greedy optimization algorithm |
| `/optimize_lp` | POST | Linear programming optimization (primary) |
| `/export_pdf` | POST | Generate PDF schedule report |

**Request/Response Formats:**
- Upload: `multipart/form-data` with file(s)
- Optimize: `application/json` with list of Route objects
- PDF Export: `application/json` with schedule, returns `application/pdf`

## Data Import/Export

**Input Formats:**
- Excel files (`.xlsx`) - Galician school bus route format (UE3617-UE3622)
  - Sheets: `I. Rutas`, `I. Rutas (2)`, `II. Paradas`, `II. Paradas (2)`, `III. Expedicions`
  - Parsed by: `backend/parser.py`

**Output Formats:**
- JSON - API responses (routes, schedules)
- PDF - Schedule export via ReportLab (`backend/pdf_service.py`)

## Third-Party Service Dependencies

| Service | Required | Fallback |
|---------|----------|----------|
| OSRM Public API | No | Haversine distance calculation |
| OpenStreetMap Tiles | Yes (for map view) | None (map won't render) |

## Network Requirements

- Outbound HTTPS to `router.project-osrm.org` (port 443)
- Outbound HTTPS to OpenStreetMap tile servers (port 443)
- Local network: Backend-Frontend communication on localhost

---

*Integration audit: 2025-01-19*
