# Dashboard Tutti - Bus Route Optimizer

## What This Is

Visual overhaul of the existing bus-route-optimizer with a "Dark Command" aesthetic. A fleet management dashboard with metrics, improved upload flow, and an optional 3D globe for visual impact. Same backend functionality, new frontend presentation.

## Core Value

Fleet managers can optimize school bus routes through a visually impressive, metrics-driven interface that makes the optimization workflow feel like a professional command center.

## Requirements

### Validated

- Upload Excel files with route data (Rutas, Paradas, Expedicions sheets) — existing
- Parse routes and display preview for verification — existing
- Run LP-based optimization to minimize fleet size — existing
- Visualize optimized routes on Leaflet map — existing
- Export PDF schedules with bus assignments — existing

### Active

- [ ] Dark theme UI with green neon / cyan blue accents
- [ ] Glass/blur card effects throughout interface
- [ ] Metrics sidebar: total routes, buses in service, total km, fleet efficiency %, total deadhead time
- [ ] Statistics panel: routes by day/week charts, distribution by zone/school
- [ ] Improved file upload with drag & drop, validation feedback, upload history
- [ ] Animated schedule playback showing where buses would be at each time
- [ ] Control panel: run optimization button, view results, export PDF, configuration params
- [ ] 3D globe visual element (bonus — not required for MVP)

### Out of Scope

- Supabase integration — deferred to future milestone
- Real GPS tracking — system shows simulated playback only
- Multiple user types — single fleet manager user
- Full TypeScript migration — only new code in TS, existing JS stays
- Mobile-specific layouts — desktop-first dashboard

## Context

**Existing System:**
- FastAPI backend with working optimization pipeline (parser → optimizer → PDF export)
- React frontend with basic file upload and Leaflet map visualization
- OSRM integration for real travel times with local caching
- PuLP-based LP solver for minimum path cover optimization

**Codebase State:**
- Backend: Python with FastAPI, well-structured with models.py, parser.py, optimizer.py, router_service.py, pdf_service.py
- Frontend: React 18 + Vite + JavaScript + Tailwind (current)
- No database — file-based data input from Excel uploads

**User:**
Single user type — fleet manager who uploads Excel schedules, runs optimization, reviews results on map, exports PDF schedules.

## Constraints

- **Tech Stack**: React + Vite + TypeScript (new code) + Tailwind CSS
- **3D Globe**: Three.js or React Three Fiber
- **Charts**: Recharts for statistics visualization
- **Compatibility**: Existing JavaScript components must continue working
- **Backend**: No changes — use existing FastAPI endpoints as-is
- **Scope**: Frontend visual overhaul only

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| TypeScript for new code only | Avoid full rewrite, ship faster | — Pending |
| Globe as visual element, not functional | Real route work stays in Leaflet, globe is aesthetic | — Pending |
| Simulated playback, not GPS | Matches current batch optimization model | — Pending |
| Supabase deferred | Focus on visual overhaul first | — Pending |

---
*Last updated: 2026-01-19 after initialization*
