# Technology Stack

**Analysis Date:** 2025-01-19

## Languages

**Primary:**
- Python 3.x - Backend API, optimization algorithms, Excel parsing, PDF generation
- JavaScript (ES6+) - Frontend React application

**Secondary:**
- JSX - React component syntax
- CSS - Styling via Tailwind CSS

## Runtime

**Environment:**
- Python: Virtual environment at `.venv/`
- Node.js: Required for frontend build and development

**Package Manager:**
- pip - Python dependencies (`backend/requirements.txt`)
- npm - JavaScript dependencies (`frontend/package.json`)
- Lockfile: `frontend/package-lock.json` (present)

## Frameworks

**Core:**
- FastAPI 0.121.x - Python REST API framework (`backend/main.py`)
- React 18.2.x - Frontend UI framework (`frontend/src/`)

**Testing:**
- No formal test framework configured (ad-hoc test scripts in `backend/test_*.py`)

**Build/Dev:**
- Vite 4.4.x - Frontend build tool and dev server (`frontend/vite.config.js`)
- uvicorn - ASGI server for FastAPI (`backend/`)

## Key Dependencies

**Backend Critical:**
- `fastapi` - REST API framework
- `uvicorn` - ASGI server
- `pandas` - Excel file reading and data manipulation
- `openpyxl` - Excel file parsing engine
- `pulp>=2.8` - Linear programming optimization solver
- `reportlab>=4.0` - PDF generation
- `requests` - HTTP client for OSRM API
- `python-multipart` - File upload handling
- `pydantic` - Data validation and serialization (bundled with FastAPI)

**Frontend Critical:**
- `react` / `react-dom` - UI framework
- `leaflet` / `react-leaflet` - Interactive map rendering
- `lucide-react` - Icon library
- `react-dropzone` - File upload drag-and-drop
- `tailwindcss` - Utility-first CSS framework

**Infrastructure:**
- `@vitejs/plugin-react` - Vite React plugin
- `postcss` / `autoprefixer` - CSS processing

## Configuration

**Environment:**
- No `.env` files detected
- Environment variables used:
  - `OSRM_URL` - Optional override for OSRM routing API (default: `https://router.project-osrm.org/route/v1/driving`)
  - `OSRM_TABLE_URL` - Optional override for OSRM table API (default: `https://router.project-osrm.org/table/v1/driving`)

**Build:**
- `frontend/vite.config.js` - Vite configuration (minimal, just React plugin)
- `frontend/tailwind.config.js` - Tailwind CSS configuration with custom colors
- `frontend/postcss.config.js` - PostCSS configuration for Tailwind

**Startup:**
- `start_tutti.bat` - Windows batch script to start both backend and frontend

## Platform Requirements

**Development:**
- Windows (batch scripts provided)
- Python 3.x with pip
- Node.js with npm
- Git

**Production:**
- Backend: Any platform supporting Python 3.x + uvicorn
- Frontend: Static hosting (Vite build output)
- External: OSRM public API access (or self-hosted OSRM)

## Scripts

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```
- Runs on: `http://localhost:8000`

**Frontend:**
```bash
cd frontend
npm install
npm run dev      # Development
npm run build    # Production build
npm run lint     # ESLint
npm run preview  # Preview production build
```
- Runs on: `http://localhost:5173`

## Data Persistence

**Cache:**
- `osrm_cache.json` - Persistent cache for OSRM travel time lookups (JSON file at project root)

**Temporary:**
- Uploaded Excel files stored temporarily as `temp_{filename}` in backend directory, deleted after parsing

---

*Stack analysis: 2025-01-19*
