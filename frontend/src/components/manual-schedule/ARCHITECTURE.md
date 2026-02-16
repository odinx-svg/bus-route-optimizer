# Arquitectura del Editor Manual de Horarios

## 📋 Resumen

Esta arquitectura define el estado global y la estructura de datos para el modo constructor manual del Editor de Horarios.

## 🏗️ Estructura de Carpetas

### Implementación Actual
```
frontend/src/components/manual-schedule/
├── README.md                          # Documentación general
├── ARCHITECTURE.md                    # Esta documentación
├── INTEGRATION.md                     # Guía de integración
├── index.js                           # Exportaciones del módulo
│
├── ManualScheduleEditor.jsx           # ✅ Componente principal
├── RoutesPalette.jsx                  # ✅ Panel de rutas
├── WorkspaceBusRow.jsx                # ✅ Fila de bus
├── RouteCard.jsx                      # ✅ Tarjeta de ruta
├── CompatibilityTooltip.jsx           # ✅ Validación visual
├── DragPreviewOverlay.jsx             # ✅ Preview drag
├── DropZoneIndicator.jsx              # ✅ Indicadores drop
└── RouteConnection.jsx                # ✅ Conexiones entre rutas
```

### Componentes de Soporte Creados
```
frontend/src/
├── stores/
│   └── manualScheduleStore.js         # Store Zustand (30KB)
├── types/
│   └── manualSchedule.ts              # Tipos TypeScript (11KB)
└── hooks/manual-schedule/
    ├── index.js                       # Exportaciones
    ├── useManualSchedule.js           # Hook CRUD
    ├── useOSRMValidation.js           # Hook validación OSRM
    └── useDragAndDrop.js              # Hook DnD
```

## 🔄 Arquitectura de Estado

### Estado Global (Zustand)

```typescript
interface ManualScheduleState {
  // Buses en construcción
  buses: BusInConstruction[];
  
  // Rutas disponibles (piezas de puzzle)
  availableRoutes: Route[];
  
  // IDs de rutas ya asignadas
  assignedRouteIds: Set<string>;
  
  // Cache de tiempos OSRM calculados
  osrmCache: Map<string, OSRMCacheEntry>;
  
  // Estado de validación
  validationStatus: 'valid' | 'invalid' | 'pending' | 'unvalidated';
  invalidPairs: InvalidRoutePair[];
}
```

### Flujo de Datos

```
┌─────────────────────────────────────────────────────────────────┐
│                     ZUSTAND STORE                               │
├─────────────────────────────────────────────────────────────────┤
│  State:                                                         │
│  ├── buses[]              ← Buses en construcción               │
│  ├── availableRoutes[]    ← Piezas disponibles                  │
│  ├── assignedRouteIds     ← Set de rutas usadas                 │
│  ├── osrmCache            ← Cache de tiempos                    │
│  └── validationStatus     ← Estado de validación                │
├─────────────────────────────────────────────────────────────────┤
│  Actions:                                                       │
│  ├── addBus(), removeBus()                                      │
│  ├── assignRoute(), unassignRoute(), moveRoute()                │
│  ├── setOSRMTime(), getOSRMTime()                               │
│  ├── validateSchedule()                                         │
│  └── exportSchedule(), importSchedule()                         │
└─────────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  RoutesPalette  │  │  WorkspaceArea  │  │  Compatibility  │
│                 │  │                 │  │  Preview        │
│ - Lista rutas   │  │ - Lista buses   │  │                 │
│ - Drag source   │  │ - Drop targets  │  │ - Tooltips      │
│ - Filtros       │  │ - Sortable      │  │ - Validación    │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## 🎨 Sistema de Colores

| Elemento | Color | Uso |
|----------|-------|-----|
| Compatible | 🟢 Verde | Transición válida entre rutas |
| Incompatible | 🔴 Rojo | Conflicto de tiempo detectado |
| Pendiente | 🟡 Amarillo | Esperando validación |
| Desconocido | ⚪ Gris | Sin datos de OSRM |
| Bus 1 | 🔵 Azul | Identificación visual |
| Bus 2 | 🟢 Verde | Identificación visual |
| Bus 3 | 🟠 Naranja | Identificación visual |

## 🔄 Drag & Drop Flow

```
1. DRAG START
   └─> RouteCard (from Palette)
       └─> onDragStart: { type: 'route', routeId }

2. DRAG OVER
   └─> WorkspaceBusRow
       └─> onDragOver: Calcular posición de inserción
       └─> Mostrar preview visual

3. DROP
   └─> WorkspaceBusRow
       └─> onDrop: assignRoute(busId, routeId)

4. DRAG END
   └─> Limpiar estados temporales
   └─> Trigger validación asíncrona
```

## 📊 Integración con OSRM

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Asignar Ruta   │────▶│  Verificar Cache │────▶│  ¿En Cache?     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                    ┌───────────────────┴───────────┐
                                   SÍ                              NO
                                    │                               │
                                    ▼                               ▼
                            ┌───────────────┐               ┌─────────────────┐
                            │  Usar Cache   │               │  Llamar OSRM    │
                            │  Inmediato    │               │  API Backend    │
                            └───────────────┘               └─────────────────┘
                                                                        │
                                                                        ▼
                                                              ┌─────────────────┐
                                                              │  Guardar en     │
                                                              │  Cache          │
                                                              └─────────────────┘
```

## ✅ Criterios de Aceptación

- [x] Estado tipado correctamente (`types/manualSchedule.ts`)
- [x] Soporte para múltiples buses dinámicos (`stores/manualScheduleStore.js`)
- [x] Cache de OSRM para no repetir llamadas (`osrmCache: Map`)
- [x] Estructura escalable (módulos separados)

## 📦 Entregables

1. ✅ `frontend/src/stores/manualScheduleStore.js` (con Zustand) - 30KB
2. ✅ `frontend/src/types/manualSchedule.ts` (tipos) - 11KB
3. ✅ `frontend/src/components/manual-schedule/README.md` (arquitectura) - 19KB
4. ✅ Estructura de carpetas creada
5. ✅ `frontend/src/hooks/manual-schedule/` (hooks personalizados)
6. ✅ `frontend/src/components/manual-schedule/INTEGRATION.md` - guía de integración
7. ✅ `frontend/src/components/manual-schedule/ARCHITECTURE.md` - esta documentación

## 🔌 Dependencias a Instalar

```bash
cd frontend
npm install zustand immer uuid
```

## 🚀 Uso del Store

```jsx
import { useManualScheduleStore } from '../stores/manualScheduleStore';

function MyComponent() {
  const { buses, addBus, assignRoute } = useManualScheduleStore();
  
  return (
    <button onClick={() => addBus()}>
      Agregar Bus
    </button>
  );
}
```

## 📝 Notas

- El store usa **Immer** para actualizaciones inmutables
- Incluye **middleware de persistencia** para localStorage
- Integrado con **Redux DevTools** para debugging
- Los hooks proporcionan **selectores optimizados**
