# Roadmap: Dashboard Tutti

**Created:** 2026-01-19
**Phases:** 6
**Mode:** Standard depth, parallel execution

## Phase Overview

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | Foundation | TypeScript + dark theme base | UI-01..06, INT-01 | 7 |
| 2 | Metrics & Charts | KPI sidebar + statistics | MET-01..04, CHT-01 | 5 |
| 3 | Upload Flow | Enhanced file upload | UPL-01..03, INT-03 | 4 |
| 4 | Control Panel | Optimization controls + map | CTL-01..03, INT-02 | 4 |
| 5 | Playback | Animated schedule visualization | CTL-04 | 1 |
| 6 | 3D Globe | Globe with route arcs | GLB-01..04 | 4 |

---

## Phase 1: Foundation

**Goal:** Establish TypeScript, dark theme, and reusable glass components

**Requirements:**
- UI-01: Dark theme with green neon / cyan blue accents
- UI-02: Glass morphism cards with backdrop-blur
- UI-03: Glow effects on key metrics
- UI-04: Animated transitions (Framer Motion)
- UI-05: Consistent typography
- UI-06: WCAG-compliant contrast
- INT-01: TypeScript setup for new components

**Success Criteria:**
1. `tsconfig.json` configured with `allowJs: true`
2. Tailwind config extended with neon/glass color palette
3. `GlassCard` component renders with blur effect
4. `NeonButton` component has glow on hover
5. Dark background (#0a0a0f) applied to app shell
6. Typography uses Inter or similar modern sans-serif
7. All new components pass contrast checker

**Dependencies:** None (foundational)

---

## Phase 2: Metrics & Charts

**Goal:** Build KPI sidebar and statistics visualization

**Requirements:**
- MET-01: Left sidebar with KPIs (routes, buses, km)
- MET-02: Fleet efficiency percentage
- MET-03: Deadhead time metric
- MET-04: Trend indicators (up/down)
- CHT-01: Routes by day/week chart

**Success Criteria:**
1. `MetricsSidebar` component displays 4+ KPIs
2. Each metric card uses `GlassCard` styling
3. Trend arrows show green (up) or red (down)
4. Recharts bar chart renders routes data
5. Chart integrates with dark theme (transparent bg, light text)

**Dependencies:** Phase 1 (GlassCard, theme)

---

## Phase 3: Upload Flow

**Goal:** Enhanced drag & drop upload with history

**Requirements:**
- UPL-01: Drag & drop with visual feedback
- UPL-02: Validation with error/success indicators
- UPL-03: Upload history panel
- INT-03: Use existing API endpoints

**Success Criteria:**
1. Drag zone highlights on file hover
2. Invalid files show error message with reason
3. Valid files show success with file info
4. Upload history persists in localStorage
5. History shows filename, date, route count
6. POST /upload endpoint called correctly

**Dependencies:** Phase 1 (GlassCard, theme)

---

## Phase 4: Control Panel

**Goal:** Optimization controls and map integration

**Requirements:**
- CTL-01: Optimize button with loading state
- CTL-02: Export PDF button
- CTL-03: Configuration modal
- INT-02: Leaflet map preserved

**Success Criteria:**
1. "Run Optimization" button shows spinner while loading
2. Button disabled during optimization
3. Export PDF triggers download
4. Config modal opens with param fields
5. Params (time, capacity, speed) saved to state
6. Existing MapView renders after optimization
7. Toggle between globe view and map view works

**Dependencies:** Phase 2 (metrics to display results), Phase 3 (upload to have data)

---

## Phase 5: Playback

**Goal:** Animated visualization of bus schedule

**Requirements:**
- CTL-04: Animated schedule playback

**Success Criteria:**
1. Timeline slider controls playback time
2. Bus positions update based on schedule times
3. Play/pause controls work
4. Speed control (1x, 2x, 4x)
5. Current time displayed

**Dependencies:** Phase 4 (needs schedule data and map)

---

## Phase 6: 3D Globe

**Goal:** Decorative globe with route visualization

**Requirements:**
- GLB-01: 3D globe background element
- GLB-02: Route arcs visualization
- GLB-03: Rotation and zoom interaction
- GLB-04: Lazy loading with suspense

**Success Criteria:**
1. Globe renders using React Three Fiber
2. r3f-globe component configured with dark earth texture
3. Route arcs show start→end with neon colors
4. OrbitControls enable rotation/zoom
5. Globe lazy loads (no blocking initial render)
6. Fallback shows loading skeleton
7. Globe sits behind glass cards (z-index layering)

**Dependencies:** Phase 1 (theme), Phase 3 (route data)

---

## Execution Order

```
Phase 1 (Foundation)
    │
    ├──────────┬──────────┐
    ▼          ▼          ▼
Phase 2    Phase 3    Phase 6
(Metrics)  (Upload)   (Globe)
    │          │
    └────┬─────┘
         ▼
     Phase 4
   (Control Panel)
         │
         ▼
     Phase 5
    (Playback)
```

**Parallel opportunities:**
- Phases 2, 3, 6 can run in parallel after Phase 1
- Phase 4 requires 2 and 3
- Phase 5 requires 4

---

## Risk Mitigation

| Risk | Mitigation | Phase |
|------|------------|-------|
| Three.js memory leaks | Use R3F disposal, lazy load | 6 |
| Backdrop-blur performance | Limit visible glass cards | 1 |
| WebGL context limits | Toggle globe/map views | 4, 6 |
| Contrast issues | Test WCAG during Phase 1 | 1 |

---

*Roadmap created: 2026-01-19*
