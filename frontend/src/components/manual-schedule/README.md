# Manual Schedule Components

Módulo de componentes para la construcción manual de horarios mediante drag & drop.

## 📋 Componentes

### RoutesPalette
Panel lateral que muestra las rutas disponibles para asignar.

```jsx
import { RoutesPalette } from './components/manual-schedule';

<RoutesPalette 
  routes={availableRoutes}
  isLoading={false}
  title="Rutas Disponibles"
  onRouteClick={handleRouteClick}
/>
```

**Props:**
- `routes` (array): Lista de rutas disponibles
- `isLoading` (boolean): Estado de carga
- `title` (string): Título del panel
- `onRouteClick` (function): Callback al hacer click en una ruta

### RouteCard
Tarjeta visual que representa una ruta. Soporta drag & drop.

```jsx
import { RouteCard } from './components/manual-schedule';

<RouteCard 
  route={route}
  isDragging={false}
  compatibility="compatible" // 'compatible' | 'incompatible' | null
/>
```

**Props:**
- `route` (object): Datos de la ruta { id, code, type, startTime, endTime, origin, destination }
- `isDragging` (boolean): Estado visual de arrastre
- `compatibility` (string): Estado de compatibilidad para resaltado visual

### WorkspaceBusRow
Fila que representa un bus en el workspace. Soporta drop de rutas.

```jsx
import { WorkspaceBusRow } from './components/manual-schedule';

<WorkspaceBusRow
  bus={{ id: 'B001', type: 'standard' }}
  routes={assignedRoutes}
  validations={{ errors: [], warnings: [] }}
  onDrop={(route, position) => handleDrop(route, position)}
  onRemoveRoute={(routeId) => handleRemove(routeId)}
/>
```

**Props:**
- `bus` (object): Datos del bus { id, type }
- `routes` (array): Rutas asignadas al bus
- `validations` (object): Resultados de validación { errors, warnings }
- `onDrop` (function): Callback al dropear una ruta
- `onRemoveRoute` (function): Callback al eliminar una ruta

## 🎯 Uso Completo

### Página ManualSchedulePage

```jsx
import { ManualSchedulePage } from './components/manual-schedule';

function App() {
  const [routes, setRoutes] = useState([]);
  
  const handleSave = async (scheduleData) => {
    // Enviar al backend
    const response = await fetch('/api/schedule', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(scheduleData),
    });
    return response.json();
  };
  
  return (
    <ManualSchedulePage 
      routes={routes}
      onSave={handleSave}
    />
  );
}
```

**Props:**
- `routes` (array): Rutas disponibles para asignar
- `onSave` (function): Callback al guardar el horario (opcional)

## 🔧 Características

### Drag & Drop
- Arrastra rutas desde el panel izquierdo a los buses
- Reordena rutas dentro de un mismo bus
- Mueve rutas entre diferentes buses
- Visualización en tiempo real durante el arrastre

### Validación en Tiempo Real
- Detecta solapamientos entre rutas
- Alerta sobre buffers cortos (< 10 min)
- Indicadores visuales de compatibilidad
- Panel de resumen de validaciones

### Persistencia
- Auto-guardado en localStorage (draft)
- Guardado manual como schedule definitivo
- Recuperación de draft al recargar la página

### Selector de Día
- Soporte para días L, M, Mc, X, V
- Cambio rápido entre días
- Horario independiente por día

## 🎨 Estilos

Los componentes usan Tailwind CSS con las siguientes convenciones:

- **Rutas de entrada (entry)**: Gradiente índigo
- **Rutas de salida (exit)**: Gradiente ámbar
- **Errores**: Rojo (`text-red-400`, `bg-red-500`)
- **Advertencias**: Ámbar (`text-amber-400`, `bg-amber-500`)
- **Éxito**: Verde (`text-green-400`, `bg-green-500`)

## 📝 Formato de Datos

### Route
```typescript
interface Route {
  id: string;
  code: string;
  type: 'entry' | 'exit';
  startTime: string; // "HH:MM"
  endTime: string;   // "HH:MM"
  origin: string;
  destination: string;
}
```

### Bus
```typescript
interface Bus {
  id: string;
  type: 'standard';
  routes: Route[];
}
```

### ScheduleData (para guardar)
```typescript
interface ScheduleData {
  day: string; // 'L' | 'M' | 'Mc' | 'X' | 'V'
  buses: {
    bus_id: string;
    items: {
      route_id: string;
      route_code: string;
      start_time: string;
      end_time: string;
      origin: string;
      destination: string;
      type: string;
      order: number;
    }[];
  }[];
  stats: {
    total_buses: number;
    total_routes: number;
    total_duration: number;
  };
}
```

## 🚀 Flujo de Trabajo

1. **Inicio**: Carga o crea un draft desde localStorage
2. **Añadir Buses**: Usa el botón "Añadir Bus" para crear nuevos buses
3. **Asignar Rutas**: Arrastra rutas desde el panel izquierdo a los buses
4. **Reorganizar**: Arrastra rutas para reordenar o mover entre buses
5. **Validar**: Revisa el panel de validación para errores/advertencias
6. **Guardar**: Guarda el horario cuando esté completo y válido

## 📦 Dependencias

- `@dnd-kit/core`: Core de drag & drop
- `@dnd-kit/sortable`: Ordenamiento sortable
- `react`: Framework UI
- Tailwind CSS: Estilos

## 🐛 Solución de Problemas

### Las rutas no se arrastran
- Verificar que las rutas tengan un `id` único
- Comprobar que `@dnd-kit/core` esté instalado

### Error al guardar
- Revisar el panel de validación para errores
- Verificar conexión con el backend
- Comprobar formato de datos de entrada

### Draft no se recupera
- Verificar que localStorage esté disponible
- Comprobar clave `manual_schedule_draft`
