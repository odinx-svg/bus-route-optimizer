---
name: tutti-frontend-dev
description: Desarrollo frontend para Tutti Fleet Optimizer. Usar cuando se necesite crear, modificar o debuggear codigo React/JSX/TypeScript en el frontend, incluyendo componentes UI, stores Zustand, hooks personalizados, integracion con API backend, drag & drop, visualizacion de mapas, o el timeline editable.
---

# Tutti Frontend Development Skill

## Stack Tecnologico

| Tecnologia | Uso |
|------------|-----|
| React 18 | Framework UI |
| Vite | Build tool |
| Zustand | State management |
| Tailwind CSS | Styling |
| @dnd-kit | Drag & drop |
| Leaflet | Mapas |
| Recharts | Graficos |
| Framer Motion | Animaciones |

## Convenciones de Codigo React

### Imports Ordenados
```javascript
// 1. React
import React, { useState, useEffect, useCallback } from 'react';

// 2. Third-party
import { Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';

// 3. Local components
import RouteBlock from './RouteBlock';
import BusRow from './BusRow';

// 4. Stores/Services/Utils
import { useTimelineStore } from '../stores/timelineStore';
import { apiService } from '../services/api.service';
```

### Componentes Funcionales

```javascript
// Props destructuring con defaults
const MapView = ({ 
  routes = [], 
  schedule = null,
  selectedBusId = null,
  onBusSelect = () => {}
}) => {
  // Estados con nombres descriptivos
  const [mapRoutes, setMapRoutes] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // useEffect con cleanup
  useEffect(() => {
    let isMounted = true;
    
    const loadData = async () => {
      if (!isMounted) return;
      // ...
    };
    
    loadData();
    
    return () => { 
      isMounted = false; 
    };
  }, [dependencies]);
  
  // Handlers memoizados
  const handleClick = useCallback((id) => {
    onBusSelect(id);
  }, [onBusSelect]);
  
  return (
    // JSX
  );
};
```

### Stores Zustand

```javascript
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';

export const useTimelineStore = create(
  immer((set, get) => ({
    // State
    routes: [],
    scheduleByDay: {},
    activeDay: 'L',
    isDirty: false,
    
    // Actions simples
    setRoutes: (routes) => set({ routes, isDirty: true }),
    setActiveDay: (day) => set({ activeDay: day }),
    
    // Actions complejas con Immer
    moveRoute: (routeId, fromBusId, toBusId) => set((state) => {
      // Logic para mover ruta entre buses
      const route = state.scheduleByDay[state.activeDay]
        .find(b => b.bus_id === fromBusId)
        ?.items.find(i => i.route_id === routeId);
      
      if (route) {
        // Remover de origen
        const fromBus = state.scheduleByDay[state.activeDay]
          .find(b => b.bus_id === fromBusId);
        fromBus.items = fromBus.items.filter(i => i.route_id !== routeId);
        
        // Agregar a destino
        const toBus = state.scheduleByDay[state.activeDay]
          .find(b => b.bus_id === toBusId);
        toBus.items.push(route);
      }
    }),
    
    // Selectors computados
    getActiveSchedule: () => {
      const state = get();
      return state.scheduleByDay[state.activeDay]?.schedule || [];
    },
  }))
);
```

## Estructura de Componentes

### Nuevo Componente

Crear en `src/components/NuevoComponente.jsx`:

```javascript
import React from 'react';

/**
 * Descripcion del componente
 */
const NuevoComponente = ({
  prop1,
  prop2 = 'default',
  onAction
}) => {
  return (
    <div className="class-tailwind">
      {/* Contenido */}
    </div>
  );
};

export default NuevoComponente;
```

### Componente con Sub-componentes

Para componentes complejos (como timeline-editable), crear carpeta:

```
components/timeline-editable/
├── index.js                 # Exportaciones publicas
├── TimelineEditable.jsx     # Componente principal
├── Workspace.jsx            # Area de trabajo
├── BusRow.jsx               # Fila de bus
├── RouteBlock.jsx           # Bloque de ruta
├── UnassignedPanel.jsx      # Panel rutas sin asignar
└── hooks/
    ├── useAutoSave.js
    └── useKeyboardShortcuts.js
```

## Drag & Drop (@dnd-kit)

### Setup Basico

```javascript
import {
  DndContext,
  useDraggable,
  useDroppable,
  DragOverlay
} from '@dnd-kit/core';

// Draggable item
const DraggableItem = ({ id, children }) => {
  const { attributes, listeners, setNodeRef, transform } = useDraggable({
    id,
  });
  
  const style = transform ? {
    transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
  } : undefined;
  
  return (
    <div ref={setNodeRef} style={style} {...listeners} {...attributes}>
      {children}
    </div>
  );
};

// Droppable area
const DroppableArea = ({ id, children }) => {
  const { isOver, setNodeRef } = useDroppable({
    id,
  });
  
  return (
    <div 
      ref={setNodeRef} 
      className={isOver ? 'bg-blue-100' : ''}
    >
      {children}
    </div>
  );
};

// Uso
const handleDragEnd = (event) => {
  const { active, over } = event;
  if (over && active.id !== over.id) {
    // Mover item de active.id a over.id
  }
};

<DndContext onDragEnd={handleDragEnd}>
  <DroppableArea id="bus-1">
    <DraggableItem id="route-1">Ruta 1</DraggableItem>
  </DroppableArea>
</DndContext>
```

## API Integration

### Servicio API

```javascript
// services/api.service.ts
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const apiService = {
  async optimizeRoutes(routes: Route[]): Promise<BusSchedule[]> {
    const response = await fetch(`${API_URL}/optimize-v6`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(routes),
    });
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Error ${response.status}`);
    }
    
    return response.json();
  },
  
  async exportPDF(schedule: BusSchedule[], dayName: string): Promise<Blob> {
    const response = await fetch(`${API_URL}/export_pdf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ schedule, day_name: dayName }),
    });
    
    if (!response.ok) {
      throw new Error('Export failed');
    }
    
    return response.blob();
  }
};
```

### Uso con Loading States

```javascript
const Component = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const handleOptimize = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const result = await apiService.optimizeRoutes(routes);
      setSchedule(result);
    } catch (err) {
      setError(err.message);
      notifications.error('Optimizacion fallida', err.message);
    } finally {
      setIsLoading(false);
    }
  };
  
  return (
    <button onClick={handleOptimize} disabled={isLoading}>
      {isLoading ? <Loader2 className="animate-spin" /> : 'Optimizar'}
    </button>
  );
};
```

## Mapas (Leaflet)

### Setup Basico

```javascript
import { MapContainer, TileLayer, Polyline, Marker } from 'react-leaflet';

const MapView = ({ routes }) => {
  return (
    <MapContainer
      center={[42.5, -8.0]}  // Galicia
      zoom={10}
      style={{ height: '100%', width: '100%' }}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; OpenStreetMap'
      />
      
      {routes.map(route => (
        <Polyline
          key={route.id}
          positions={route.stops.map(s => [s.lat, s.lon])}
          color={route.type === 'entry' ? '#3b82f6' : '#10b981'}
        />
      ))}
    </MapContainer>
  );
};
```

## Estilos (Tailwind)

### Convenciones

```javascript
// Layout
className="flex flex-col h-full p-4 gap-3"

// Estados
className={`
  px-3 py-2 rounded-md
  ${isActive ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700'}
  ${isDisabled && 'opacity-50 cursor-not-allowed'}
`}

// Responsive
className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
```

### Colores del Sistema

```javascript
// Primary
bg-[#0b141f]        // Fondo oscuro
bg-[#1a2d3f]        // Panel
border-[#253a4f]    // Bordes
text-[#64b5f6]      // Azul acento

// Estados
bg-emerald-500      // Exito
bg-amber-500        // Advertencia
bg-red-500          // Error
```

## Notificaciones

```javascript
import { notifications } from '../services/notifications';

// Tipos
notifications.success('Titulo', 'Mensaje');
notifications.error('Error', err.message);
notifications.warning('Atencion', 'Mensaje');
notifications.info('Info', 'Mensaje');
notifications.loading('Cargando...');  // Retorna ID para dismiss

// Dismiss
const id = notifications.loading('Procesando...');
notifications.dismiss(id);
```

## Referencias

- `references/component-patterns.md`: Patrones de componentes
- `references/timeline-architecture.md`: Arquitectura del timeline
