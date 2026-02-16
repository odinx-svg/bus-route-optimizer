# Guía de Integración - Manual Schedule Editor

## 🚀 Instalación de Dependencias

```bash
cd frontend
npm install zustand immer uuid
```

## 🔌 Integración con la Aplicación Existente

### 1. Agregar al Router/App

```jsx
// App.jsx
import { ManualScheduleEditor } from './components/manual-schedule';

function App() {
  return (
    <Routes>
      <Route path="/upload" element={<FileUpload />} />
      <Route path="/optimize" element={<OptimizationView />} />
      <Route path="/manual-schedule" element={<ManualScheduleEditorPage />} />
    </Routes>
  );
}

function ManualScheduleEditorPage() {
  const location = useLocation();
  const initialRoutes = location.state?.routes || [];
  
  return <ManualScheduleEditor initialRoutes={initialRoutes} />;
}
```

### 2. Flujo desde Upload

```jsx
// FileUpload.jsx
import { useNavigate } from 'react-router-dom';
import { apiService } from '../services/api.service';

function FileUpload() {
  const navigate = useNavigate();
  
  const handleUpload = async (files) => {
    try {
      const routes = await apiService.uploadFiles(files);
      
      // Redirigir al editor manual con las rutas
      navigate('/manual-schedule', { 
        state: { routes } 
      });
    } catch (error) {
      // Manejar error
    }
  };
  
  // ...
}
```

### 3. Integración con Optimización Automática

```jsx
// Toolbar.jsx (dentro del editor manual)
import { apiService } from '../../../services/api.service';

function OptimizeButton() {
  const { buses, availableRoutes, setAvailableRoutes } = useManualScheduleStore();
  
  const handleOptimize = async () => {
    // Convertir estado actual a formato para el solver
    const unassignedRoutes = availableRoutes.filter(
      r => !assignedRouteIds.has(r.route_id)
    );
    
    try {
      const optimized = await apiService.optimize(unassignedRoutes);
      
      // Merge resultado con estado actual
      // (agregar nuevos buses del resultado a los existentes)
    } catch (error) {
      console.error('Optimización fallida:', error);
    }
  };
  
  return (
    <button onClick={handleOptimize}>
      Optimizar Restantes
    </button>
  );
}
```

## 📊 Estructura de Datos Esperada

### Input: Rutas desde Upload

```typescript
interface Route {
  route_id: string;
  route_name: string;
  school: string;
  stops: Array<{
    stop_id: string;
    stop_name: string;
    latitude: number;
    longitude: number;
  }>;
  start_time: string;  // "07:30"
  end_time: string;    // "08:15"
  duration_minutes: number;
  start_coords: [number, number];  // [lat, lng]
  end_coords: [number, number];    // [lat, lng]
}
```

### Output: Horario para Exportar

```typescript
interface ExportedSchedule {
  version: string;
  exportedAt: string;
  buses: Array<{
    busId: string;
    busName: string;
    color: string;
    assignedRoutes: Array<{
      routeId: string;
      startTime: string;
      endTime: string;
      position: number;
    }>;
  }>;
}
```

## 🔄 Flujo de Datos Completo

```
┌─────────────┐    Upload    ┌─────────────┐    Assign    ┌─────────────┐
│   Excel     │─────────────▶│   Routes    │─────────────▶│    Bus 1    │
│   Files     │              │   Palette   │              │   [R1,R2]   │
└─────────────┘              └─────────────┘              ├─────────────┤
                                                          │    Bus 2    │
                                                          │    [R3]     │
                                                          └──────┬──────┘
                                                                 │
                                                                 │ Validate
                                                                 ▼
                                                          ┌─────────────┐
                                                          │    OSRM     │
                                                          │    Cache    │
                                                          └──────┬──────┘
                                                                 │
                                                                 ▼
                                                          ┌─────────────┐
                                                          │   Export    │
                                                          │    PDF      │
                                                          └─────────────┘
```

## 🛠️ API Endpoints Requeridos

### 1. OSRM Time Endpoint

```typescript
// POST /api/osrm/time
interface Request {
  fromLat: number;
  fromLng: number;
  toLat: number;
  toLng: number;
}

interface Response {
  durationMinutes: number;  // Tiempo de viaje
  distanceMeters: number;   // Distancia
  geometry?: string;        // Polyline codificada
}
```

### 2. Validate Schedule Endpoint

```typescript
// POST /api/schedule/validate
interface Request {
  assignments: Array<{
    busId: string;
    routeId: string;
    startTime: string;
  }>;
}

interface Response {
  isValid: boolean;
  conflicts: Array<{
    busId: string;
    routeA: string;
    routeB: string;
    reason: string;
  }>;
}
```

## 📝 Notas de Implementación

1. **Cache OSRM**: El store mantiene un cache en memoria. Para persistencia entre sesiones, considerar localStorage.

2. **Validación**: La validación se ejecuta:
   - Después de cada operación DnD
   - Al cambiar horarios manualmente
   - Periódicamente (debounced)

3. **Undo/Redo**: Futura mejora - implementar historial de acciones en el store.

4. **Persistencia**: El store usa Zustand con persist middleware para guardar en localStorage.
