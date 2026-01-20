# Requirements: Dashboard Tutti

**Defined:** 2026-01-19
**Core Value:** Fleet managers can optimize school bus routes through a visually impressive, metrics-driven interface

## v1 Requirements

### UI Foundation

- [ ] **UI-01**: Dark theme with green neon (#39FF14) and cyan blue (#00D4FF) accents
- [ ] **UI-02**: Glass morphism cards with backdrop-blur and subtle borders
- [ ] **UI-03**: Glow effects on key metrics and interactive elements
- [ ] **UI-04**: Animated transitions using Framer Motion (entrance, hover, state changes)
- [ ] **UI-05**: Consistent typography with modern sans-serif font
- [ ] **UI-06**: WCAG-compliant contrast ratios for readability

### Metrics Dashboard

- [ ] **MET-01**: Left sidebar displaying KPIs (total routes, buses in service, total km)
- [ ] **MET-02**: Fleet efficiency percentage with visual indicator
- [ ] **MET-03**: Total deadhead time metric
- [ ] **MET-04**: Trend indicators showing changes (up/down arrows)

### Statistics Charts

- [ ] **CHT-01**: Routes by day/week bar chart using Recharts

### File Upload

- [ ] **UPL-01**: Drag & drop file upload zone with visual feedback
- [ ] **UPL-02**: File validation with error/success indicators
- [ ] **UPL-03**: Upload history panel showing previously uploaded files

### Control Panel

- [ ] **CTL-01**: Run optimization button with loading spinner state
- [ ] **CTL-02**: Export PDF button integrated in control area
- [ ] **CTL-03**: Configuration modal for parameters (time between routes, capacity, speed)
- [ ] **CTL-04**: Animated schedule playback showing bus positions over time

### 3D Globe

- [ ] **GLB-01**: 3D globe as background visual element using React Three Fiber
- [ ] **GLB-02**: Route arcs visualization showing start/end points
- [ ] **GLB-03**: Rotation and zoom interaction controls
- [ ] **GLB-04**: Lazy loading with suspense fallback

### Integration

- [ ] **INT-01**: TypeScript setup for new components (allowJs for existing)
- [ ] **INT-02**: Existing Leaflet map preserved for detailed route view
- [ ] **INT-03**: Existing API endpoints used without modification

## v2 Requirements

### Enhanced Metrics

- **MET-05**: Animated counting numbers on KPI load
- **MET-06**: Spark line mini-charts in metric cards

### Additional Charts

- **CHT-02**: Distribution by zone/school pie chart
- **CHT-03**: Efficiency comparison chart (before/after optimization)

### Upload Enhancements

- **UPL-04**: Route preview table before optimization

### Globe Enhancements

- **GLB-05**: Animated bus movement along arcs
- **GLB-06**: Time-of-day lighting effects

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real GPS tracking | System shows simulated playback only |
| Supabase integration | Deferred to future milestone |
| Multiple user types | Single fleet manager user |
| Mobile-specific layouts | Desktop-first dashboard |
| Full TypeScript migration | Only new code in TS |
| Backend changes | Frontend overhaul only |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| UI-01 | Phase 1 | Complete |
| UI-02 | Phase 1 | Complete |
| UI-03 | Phase 1 | Complete |
| UI-04 | Phase 1 | Complete |
| UI-05 | Phase 1 | Complete |
| UI-06 | Phase 1 | Complete |
| MET-01 | Phase 2 | Pending |
| MET-02 | Phase 2 | Pending |
| MET-03 | Phase 2 | Pending |
| MET-04 | Phase 2 | Pending |
| CHT-01 | Phase 2 | Pending |
| UPL-01 | Phase 3 | Pending |
| UPL-02 | Phase 3 | Pending |
| UPL-03 | Phase 3 | Pending |
| CTL-01 | Phase 4 | Pending |
| CTL-02 | Phase 4 | Pending |
| CTL-03 | Phase 4 | Pending |
| CTL-04 | Phase 5 | Pending |
| GLB-01 | Phase 6 | Pending |
| GLB-02 | Phase 6 | Pending |
| GLB-03 | Phase 6 | Pending |
| GLB-04 | Phase 6 | Pending |
| INT-01 | Phase 1 | Complete |
| INT-02 | Phase 4 | Pending |
| INT-03 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0 ✓

---
*Requirements defined: 2026-01-19*
*Last updated: 2026-01-20 after Phase 1 completion*
