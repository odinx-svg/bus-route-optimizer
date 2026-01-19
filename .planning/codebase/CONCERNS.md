# Codebase Concerns

**Analysis Date:** 2025-01-19

## Tech Debt

**Optimizer Code Complexity:**
- Issue: `backend/optimizer.py` is 1076 lines with multiple optimization phases tightly coupled (greedy, LP, merging, compaction, elimination)
- Files: `backend/optimizer.py`
- Impact: Difficult to test individual phases; changes in one algorithm can cascade unexpectedly
- Fix approach: Extract each optimization phase into separate modules (e.g., `backend/optimizer/greedy.py`, `backend/optimizer/lp.py`, `backend/optimizer/compaction.py`)

**Monkey-Patching for State:**
- Issue: `BusSchedule` objects are monkey-patched with `last_loc` attribute during optimization: `new_bus.last_loc = job['end_loc']`
- Files: `backend/optimizer.py` (lines 218, 224, 493, 617)
- Impact: Fragile state management; Pydantic model does not enforce this field
- Fix approach: Add `last_loc` properly to BusSchedule model or use a separate internal data structure for optimization state

**Hardcoded API URLs in Frontend:**
- Issue: Backend API URLs are hardcoded to `http://localhost:8000` in multiple components
- Files: `frontend/src/App.jsx` (lines 39, 63), `frontend/src/components/FileUpload.jsx` (line 29)
- Impact: Cannot deploy to different environments without code changes
- Fix approach: Use environment variable via `import.meta.env.VITE_API_URL` or centralized config

**Debug Files in Repository:**
- Issue: 31 Python files in backend, 17 of which appear to be debug/test/verification scripts not used in production
- Files: `backend/debug_*.py`, `backend/verify_*.py`, `backend/diagnose_*.py`, `backend/analyze_*.py`, `backend/reproduce_issue.py`
- Impact: Cluttered codebase; confusion about which files are production code
- Fix approach: Move scripts to `backend/scripts/` directory or remove unused ones

**Excessive Print Statements:**
- Issue: 277 `print()` calls scattered across 27 backend Python files
- Files: Most files in `backend/` (see list above)
- Impact: Log noise; no structured logging; hard to debug production issues
- Fix approach: Replace with proper `logger.debug()` / `logger.info()` calls; remove console debugging

## Known Bugs

**Unused Import Duplication:**
- Symptoms: `from router_service import get_real_travel_time, get_route_duration` imported twice in optimizer.py
- Files: `backend/optimizer.py` (lines 15 and 241)
- Trigger: N/A (just code smell)
- Workaround: None needed, but clutters code

**Temporary File Cleanup Race Condition:**
- Symptoms: Potential file lock issues on Windows with `time.sleep(0.1)` workaround
- Files: `backend/main.py` (lines 51-58)
- Trigger: Rapid file uploads on Windows
- Workaround: Current `time.sleep(0.1)` delay; should use proper context management

## Security Considerations

**CORS Allows All Origins:**
- Risk: Any website can make requests to the API, potentially leading to CSRF or data exfiltration
- Files: `backend/main.py` (line 16): `allow_origins=["*"]`
- Current mitigation: Local development only
- Recommendations: In production, restrict to specific frontend domain; add CORS origin validation

**No Input Validation on File Upload:**
- Risk: Malicious Excel files could exploit pandas vulnerabilities or cause DoS via large files
- Files: `backend/main.py` `/upload` endpoint, `backend/parser.py`
- Current mitigation: None - accepts any Excel file
- Recommendations: Add file size limits; validate Excel structure before full parsing; sandbox file processing

**Temp Files Written to Current Directory:**
- Risk: Predictable temp file paths could lead to race conditions or symlink attacks
- Files: `backend/main.py` (line 33): `file_location = f"temp_{file.filename}"`
- Current mitigation: Files deleted after processing
- Recommendations: Use `tempfile.NamedTemporaryFile()` with proper permissions

**External API Dependency (OSRM):**
- Risk: Public OSRM API could be rate-limited, unavailable, or serve malicious data
- Files: `backend/router_service.py`, `frontend/src/services/RouteService.js`
- Current mitigation: Fallback to Haversine calculation; local cache
- Recommendations: Add request timeout handling (currently 5-10s); validate OSRM response structure; consider self-hosting OSRM for production

## Performance Bottlenecks

**O(N^2) Pairwise Analysis:**
- Problem: `optimize_routes_lp` performs O(N^2) pairwise job comparison with OSRM calls
- Files: `backend/optimizer.py` (lines 311-365)
- Cause: Every job pair is evaluated for feasibility even when clearly impossible
- Improvement path: Pre-filter pairs by time window overlap before computing travel time; use spatial indexing

**Sequential OSRM Fetches in MapView:**
- Problem: Frontend fetches route geometries sequentially, one API call per route
- Files: `frontend/src/components/MapView.jsx` (lines 99-124)
- Cause: Nested async loop awaits each `fetchRouteGeometry` sequentially
- Improvement path: Use `Promise.all()` to parallelize OSRM requests; add client-side caching

**Cache Saved on Every Matrix Update:**
- Problem: `save_cache()` writes entire JSON file after every matrix chunk
- Files: `backend/router_service.py` (lines 200-201)
- Cause: Synchronous file write in hot loop
- Improvement path: Batch cache saves; use async file I/O; or use SQLite for cache

## Fragile Areas

**Time Parsing Logic:**
- Files: `backend/parser.py` (function `parse_time_value`)
- Why fragile: Handles 7+ different time formats (time object, datetime, string variations, float); easy to break with new Excel format
- Safe modification: Add comprehensive unit tests for each format before changes
- Test coverage: None detected for parser

**Optimizer Chain Reconstruction:**
- Files: `backend/optimizer.py` (lines 386-495)
- Why fragile: Complex chain-building logic with time shift calculations; break detection depends on accumulated shifts
- Safe modification: Add integration tests with known input/output pairs
- Test coverage: Only minimal test file exists (`backend/test_optimizer.py` - 38 lines, basic smoke test)

**Morning/Afternoon Classification:**
- Files: `backend/optimizer.py` (function `emparejar_turnos_manana_tarde`, lines 513-633)
- Why fragile: Uses hardcoded time boundaries (12:00, 13:00) for classification; Galician school schedules may vary
- Safe modification: Make time boundaries configurable constants
- Test coverage: None

## Scaling Limits

**In-Memory Schedule Processing:**
- Current capacity: Works well for ~100-200 routes (tested with 5 Excel files)
- Limit: Memory usage grows with route count; no streaming processing
- Scaling path: Process routes in batches; use database for intermediate results

**Single-Threaded Optimization:**
- Current capacity: Processes one optimization request at a time
- Limit: Long-running LP optimization blocks other requests
- Scaling path: Use background task queue (Celery, FastAPI BackgroundTasks)

**Public OSRM API:**
- Current capacity: Subject to public API rate limits
- Limit: Unknown but likely ~1000 requests/minute based on usage policy
- Scaling path: Self-host OSRM with regional OSM extract; cache aggressively

## Dependencies at Risk

**PuLP LP Solver:**
- Risk: Optional dependency with `pulp = None` fallback that breaks `/optimize_lp` endpoint
- Impact: Silent failure if not installed; API returns 500 error
- Migration plan: Make pulp a required dependency; add startup check

**ReportLab PDF Generation:**
- Risk: Complex table styling with hardcoded layouts; breaks if schedule structure changes
- Impact: PDF export fails or renders incorrectly
- Migration plan: Add PDF rendering tests; consider WeasyPrint as alternative

## Missing Critical Features

**No Authentication:**
- Problem: API is completely open; anyone can upload files and run optimization
- Blocks: Production deployment with multiple users; audit trail

**No Persistent Storage:**
- Problem: All data is in-memory; schedules are lost on server restart
- Blocks: Saving/loading previous optimizations; historical analysis

**No Rate Limiting:**
- Problem: No protection against API abuse
- Blocks: Safe public deployment

## Test Coverage Gaps

**Parser Module:**
- What's not tested: Excel column detection, time parsing edge cases, stop ordering
- Files: `backend/parser.py`
- Risk: Excel format changes could silently break parsing
- Priority: High

**Optimizer Core Logic:**
- What's not tested: Time window violations, chain breaking, underutilized bus elimination
- Files: `backend/optimizer.py`
- Risk: Regression in fleet size or schedule validity
- Priority: High

**API Endpoints:**
- What's not tested: File upload validation, error responses, PDF generation
- Files: `backend/main.py`
- Risk: API contract breaks without notice
- Priority: Medium

**Frontend Components:**
- What's not tested: All React components have zero test coverage
- Files: `frontend/src/components/*.jsx`, `frontend/src/App.jsx`
- Risk: UI regressions; broken user flows
- Priority: Medium

---

*Concerns audit: 2025-01-19*
