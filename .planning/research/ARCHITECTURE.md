# Architecture Research

## Component Structure

Recommended hierarchy for dashboard with 3D globe:

```
src/
├── App.jsx (existing - kept as entry)
├── main.jsx (existing - kept)
├── components/
│   ├── existing/           # Keep existing JS components
│   │   ├── MapView.jsx
│   │   ├── FileUpload.jsx
│   │   └── ...
│   │
│   └── dashboard/          # New TypeScript components
│       ├── Dashboard.tsx           # Main layout container
│       ├── Sidebar/
│       │   ├── MetricsSidebar.tsx  # Left sidebar with KPIs
│       │   ├── MetricCard.tsx
│       │   └── StatsSidebar.tsx    # Right sidebar with charts
│       ├── Globe/
│       │   ├── GlobeScene.tsx      # R3F Canvas wrapper
│       │   ├── GlobeComponent.tsx  # r3f-globe config
│       │   └── RouteArcs.tsx       # Route visualization
│       ├── Charts/
│       │   ├── RoutesByDayChart.tsx
│       │   ├── EfficiencyChart.tsx
│       │   └── DistributionChart.tsx
│       ├── Upload/
│       │   ├── UploadPanel.tsx     # Enhanced drag-drop
│       │   ├── FileHistory.tsx
│       │   └── ValidationFeedback.tsx
│       ├── Control/
│       │   ├── ControlPanel.tsx
│       │   ├── OptimizeButton.tsx
│       │   └── ConfigModal.tsx
│       └── common/
│           ├── GlassCard.tsx
│           ├── NeonButton.tsx
│           └── AnimatedNumber.tsx
```

## Three.js Integration

**Isolation strategy:**

Three.js/R3F runs in its own Canvas element, separate from React DOM:

```tsx
// GlobeScene.tsx
import { Canvas } from '@react-three/fiber'
import { Suspense } from 'react'

export function GlobeScene({ routes }) {
  return (
    <div className="absolute inset-0 -z-10"> {/* Behind glass cards */}
      <Canvas camera={{ position: [0, 0, 300] }}>
        <Suspense fallback={null}>
          <GlobeComponent routes={routes} />
          <ambientLight intensity={0.5} />
        </Suspense>
      </Canvas>
    </div>
  )
}
```

**Why isolation:**
- Canvas doesn't interfere with DOM event handling
- Can lazy-load entire 3D scene
- Performance issues isolated to Canvas
- Easy to disable for low-end devices

**r3f-globe integration:**

```tsx
import Globe from 'r3f-globe'

export function GlobeComponent({ routes }) {
  const arcsData = routes.map(route => ({
    startLat: route.stops[0].lat,
    startLng: route.stops[0].lon,
    endLat: route.stops[route.stops.length-1].lat,
    endLng: route.stops[route.stops.length-1].lon,
    color: route.type === 'entry' ? '#39FF14' : '#00D4FF'
  }))

  return (
    <Globe
      globeImageUrl="//unpkg.com/three-globe/example/img/earth-dark.jpg"
      arcsData={arcsData}
      arcColor="color"
      arcStroke={0.5}
      atmosphereColor="#00D4FF"
    />
  )
}
```

## State Management

**Keep existing useState pattern**, but organize:

```tsx
// types/dashboard.ts
interface DashboardState {
  // Data
  routes: Route[]
  schedule: BusSchedule[] | null

  // UI
  isOptimizing: boolean
  uploadHistory: UploadEntry[]
  activeView: 'globe' | 'map' | 'table'

  // Config
  config: OptimizationConfig
}

// hooks/useDashboard.ts
export function useDashboard() {
  const [routes, setRoutes] = useState<Route[]>([])
  const [schedule, setSchedule] = useState<BusSchedule[] | null>(null)
  const [isOptimizing, setIsOptimizing] = useState(false)
  // ... etc

  // Derived metrics
  const metrics = useMemo(() => ({
    totalRoutes: routes.length,
    totalBuses: schedule?.length ?? 0,
    totalKm: calculateTotalKm(schedule),
    efficiency: calculateEfficiency(schedule),
    deadheadTime: calculateDeadhead(schedule)
  }), [routes, schedule])

  return { routes, schedule, metrics, /* actions */ }
}
```

**No need for Redux/Zustand** — app is single-user, single-view. useState + context sufficient.

## TypeScript + JavaScript Coexistence

**tsconfig.json setup:**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "allowJs": true,          // Allow JS files
    "checkJs": false,         // Don't type-check JS
    "skipLibCheck": true,
    "noEmit": true,
    "isolatedModules": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules"]
}
```

**Import patterns:**

```tsx
// New TS file importing existing JS
import MapView from '../existing/MapView'  // Works, typed as 'any'

// Add .d.ts for frequently used JS components
// types/existing.d.ts
declare module '../components/MapView' {
  export interface MapViewProps {
    schedule: BusSchedule[]
    center: [number, number]
  }
  const MapView: React.FC<MapViewProps>
  export default MapView
}
```

## Data Flow

```
Excel Upload
     │
     ▼
┌─────────────────┐
│  POST /upload   │ ◄── UploadPanel.tsx
└────────┬────────┘
         │ routes[]
         ▼
┌─────────────────┐
│  Dashboard      │ ◄── useDashboard() state
│  State          │
└────────┬────────┘
         │
    ┌────┴────┬──────────┬──────────┐
    ▼         ▼          ▼          ▼
 Globe    Metrics    Charts    MapView
 (R3F)    Sidebar    (Recharts) (Leaflet)

User clicks "Optimize"
         │
         ▼
┌─────────────────┐
│ POST /optimize_lp│ ◄── ControlPanel.tsx
└────────┬────────┘
         │ schedule[]
         ▼
┌─────────────────┐
│  Dashboard      │
│  State          │ ─► Update all visualizations
└─────────────────┘
```

**API calls stay in services:**

```tsx
// services/api.ts
export async function uploadFiles(files: File[]): Promise<Route[]> {
  const formData = new FormData()
  files.forEach(f => formData.append('files', f))
  const res = await fetch('/upload', { method: 'POST', body: formData })
  return res.json()
}

export async function optimize(routes: Route[]): Promise<BusSchedule[]> {
  const res = await fetch('/optimize_lp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(routes)
  })
  return res.json()
}
```

---

*Research date: 2026-01-19*
