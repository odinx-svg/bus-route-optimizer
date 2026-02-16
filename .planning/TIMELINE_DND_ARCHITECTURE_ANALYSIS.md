# 📊 Análisis de Arquitectura: Timeline + Drag & Drop

## 🎯 Resumen Ejecutivo

El proyecto ya cuenta con una **implementación completa de DnD** usando `@dnd-kit` en el componente `DraggableSchedule`. El `Timeline` actual es **visualmente estático** y no tiene DnD integrado. Este análisis documenta cómo integrar DnD al Timeline existente.

---

## 1️⃣ Flujo de Datos Actual

```
┌─────────────────────────────────────────────────────────────────┐
│                        FLUJO DE DATOS                          │
└─────────────────────────────────────────────────────────────────┘

Backend (API)
     │
     ▼
App.jsx ──► scheduleByDay[activeDay].schedule
     │
     ├──► viewMode='timeline'
     │         │
     │         ▼
     │    TimelineZoomable ──► [hourRange] estado local
     │         │
     │         ▼
     │    Timeline (props: schedule, hourRange, selectedBusId, onBusSelect)
     │         │
     │         ▼
     │    useTimeline(schedule, hourRange)
     │         │
     │         ├──► busesWithPositions[] (con left%, width% calculados)
     │         └──► hourMarks[]
     │
     └──► viewMode='constructor'
               │
               ▼
          DraggableSchedule (YA TIENE DnD)
               │
               ▼
          DragAndDropContext (@dnd-kit)
               │
               ▼
          BusColumn + SortableRoute
```

---

## 2️⃣ Estructura de Componentes del Timeline

```
TimelineZoomable
│   Props: schedule, selectedBusId, onBusSelect
│   State: hourRange [6, 22]
│
└──► Timeline
     │   Props: schedule, hourRange, selectedBusId, onBusSelect
     │   Hook: useTimeline()
     │
     ├──► Header (Horas)
     │    └── hourMarks.map() ──► Marcas de hora con left%
     │
     ├──► Bus Rows (Fila por cada bus)
     │    └── busesWithPositions.map(bus =>
     │         ├──► Bus Label (izquierda, fijo)
     │         │
     │         ├──► Hour Grid Lines (líneas verticales)
     │         │
     │         └──► RouteBlock[] (componente clave para DnD)
     │              └──► Bloque visual de cada ruta
     │                   Props: item, index, isSelected
     │                   Style: { left: `${left}%`, width: `${width}%` }
     │
     └──► Legend (indicadores Entrada/Salida)
```

---

## 3️⃣ Formato Exacto de Datos

### 📦 schedule (Input - desde API/App.jsx)

```javascript
[
  {
    "bus_id": "BUS_001",
    "items": [
      {
        "route_id": "R001",
        "type": "entry",           // "entry" | "exit"
        "start_time": "07:30",
        "end_time": "08:15",
        "school_name": "Colegio San José",
        "shift_minutes": 0         // minutos de desplazamiento
      },
      {
        "route_id": "R002", 
        "type": "exit",
        "start_time": "14:00",
        "end_time": "14:45",
        "school_name": "Colegio San José",
        "shift_minutes": 0
      }
    ]
  },
  {
    "bus_id": "BUS_002",
    "items": [...]
  }
]
```

### 🎯 item procesado (después de useTimeline)

```javascript
{
  // Propiedades originales
  "route_id": "R001",
  "type": "entry",
  "start_time": "07:30",
  "end_time": "08:15",
  "school_name": "Colegio San José",
  "shift_minutes": 0,
  
  // Calculadas por useTimeline
  "left": 9.375,           // % posición desde izquierda
  "width": 7.5,            // % ancho del bloque
  "startMinutes": 450,     // minutos desde 00:00
  "endMinutes": 495        // minutos desde 00:00
}
```

### 📐 Cálculo de Posiciones (useTimeline.js)

```javascript
// Fórmula para left%
left = ((startMinutes / 60) - startHour) / totalHours * 100

// Fórmula para width%
width = ((endMinutes - startMinutes) / 60) / totalHours * 100

// Ejemplo: 07:30 - 08:15, rango 6:00-22:00 (16h)
startHour = 6, totalHours = 16
startMinutes = 450 (7*60 + 30)
left = ((450/60) - 6) / 16 * 100 = (7.5 - 6) / 16 * 100 = 9.375%

width = ((495 - 450) / 60) / 16 * 100 = (45/60) / 16 * 100 = 4.687%
```

---

## 4️⃣ Arquitectura DnD Existente (DraggableSchedule)

### Dependencias Instaladas

```json
{
  "@dnd-kit/core": "^6.3.1",
  "@dnd-kit/sortable": "^10.0.0", 
  "@dnd-kit/utilities": "^3.2.2"
}
```

### Componentes DnD Actuales

| Componente | Props Clave | Descripción |
|------------|-------------|-------------|
| `DragAndDropContext` | schedule, onScheduleChange | Provider de @dnd-kit |
| `BusColumn` | bus, selectedRouteId, onRouteSelect | Columna droppable |
| `SortableRoute` | route, busId, isSelected, onClick | Item arrastrable (vertical) |
| `DraggableRouteCard` | route, disabled, onClick | Tarjeta desde palette |
| `DropZone` | id, data, acceptTypes, validationFn | Zona de drop genérica |

### Handlers de DnD Existentes

```javascript
// DragAndDropContext.jsx
handleDragEnd(event) {
  const { active, over } = event;
  
  // Caso 1: Mover ruta entre buses (mismo bus o diferente)
  if (activeData?.type === 'route' && overData?.type === 'route') {
    moveRouteBetweenBuses(schedule, routeId, fromBusId, toBusId, overRouteId)
  }
  
  // Caso 2: Mover a bus vacío
  if (activeData?.type === 'route' && overData?.type === 'bus') {
    moveRouteToBus(schedule, routeId, fromBusId, toBusId)
  }
}
```

---

## 5️⃣ Puntos de Integración DnD para Timeline

### 🎯 Componentes a Modificar

```
┌─────────────────────────────────────────────────────────────┐
│                    INTEGRACIÓN DND                          │
└─────────────────────────────────────────────────────────────┘

1. TimelineZoomable
   └─► AGREGAR: Envolver con DragAndDropProvider
   
   <DragAndDropProvider 
     schedule={schedule} 
     onScheduleChange={handleScheduleChange}
   >
     <Timeline ... />
   </DragAndDropProvider>

2. Timeline
   └─► MODIFICAR: RouteBlock → DraggableRouteBlock
   
   // Reemplazar:
   <RouteBlock item={item} ... />
   
   // Por:
   <SortableRouteBlock 
     item={item} 
     busId={bus.bus_id}
     ...
   />

3. RouteBlock (NUEVO COMPONENTE)
   └─► CREAR: Versión sortable del bloque de ruta
   
   - useSortable() de @dnd-kit/sortable
   - Mantener estilos visuales actuales
   - Drag handle (opcional: toda el área o solo handle)
```

### 📍 Ubicaciones Exactas de Drop Zones

```
CADA FILA DE BUS (Timeline.jsx línea 52-89):

┌──────────────────────────────────────────────────────────────┐
│ BUS_001  │  ╔═══════════╗              ╔═══════════╗        │
│          │  ║  R001-E   ║   [drop]     ║  R002-X   ║        │
│          │  ╚═══════════╝              ╚═══════════╝        │
│          │  ▲                                   ▲            │
│          │  └── RouteBlock (Draggable)          │            │
│          │                                      │            │
│          │  ┌───────────────────────────────────┘            │
│          │  │ Drop zones entre bloques                      │
│          │  │ (para reordenar)                              │
│          │                                                  │
│          │  ┌────────────────────────────────────────────┐  │
│          │  │ ZONA DROP VACÍA (para agregar al final)    │  │
│          │  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘

TIPOS DE DROP ZONES NECESARIAS:

1. Entre RouteBlocks (reordenar dentro del mismo bus)
   - ID: `${busId}-insert-${index}`
   - Tipo: 'list-insert'
   
2. Área vacía de la fila (agregar al final)
   - ID: `${busId}-empty`
   - Tipo: 'bus'
   
3. Entre filas de buses (mover a otro bus)
   - Usar el contenedor de la fila como droppable
```

---

## 6️⃣ Problemas Potenciales y Soluciones

### ⚠️ Problema 1: Posicionamiento Absoluto vs DnD

**Descripción:** `RouteBlock` usa `position: absolute` con `left%` y `width%`, pero @dnd-kit funciona mejor con layouts de flujo.

**Impacto:** ALTO

**Soluciones:**
```javascript
// Opción A: Mantener posicionamiento, usar DnD solo para "mover a otro bus"
// - No permitir reordenar visualmente en la misma fila
// - Solo drag entre filas

// Opción B: Crear versión "modo edición" del Timeline
// - Al activar modo edición, cambiar a layout de lista vertical
// - Similar a DraggableSchedule pero con información temporal

// Opción C: DnD horizontal (más complejo)
// - Crear drop zones invisibles entre horas
// - Calcular nueva posición basada en X del drop
// - Requeriría re-calcul de start_time/end_time
```

### ⚠️ Problema 2: Zoom y DnD

**Descripción:** El Timeline tiene zoom (4h-20h de rango). Al hacer zoom, las posiciones cambian.

**Impacto:** MEDIO

**Solución:**
```javascript
// El DnD debe trabajar con IDs, no con posiciones
// La posición visual se recalcula automáticamente por useTimeline
// No afecta la lógica de DnD
```

### ⚠️ Problema 3: Scroll Horizontal + Drag

**Descripción:** El timeline tiene scroll horizontal (`overflow-x-auto`).

**Impacto:** MEDIO

**Solución:**
```javascript
// @dnd-kit soporta auto-scroll
// Configurar DndContext con:
<DndContext
  autoScroll={{ 
    threshold: { x: 0.1, y: 0 },  // 10% desde borde
    acceleration: 10
  }}
>
```

### ⚠️ Problema 4: Solapamiento de Rutas

**Descripción:** Las rutas pueden solaparse visualmente (mismo horario).

**Impacto:** BAJO (visual)

**Solución:**
```css
/* Asegurar z-index durante drag */
.RouteBlock.isDragging {
  z-index: 100;
  box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}
```

### ⚠️ Problema 5: Selección vs Drag

**Descripción:** Click para seleccionar vs click para iniciar drag.

**Impacto:** MEDIO

**Solución:**
```javascript
// Usar activationConstraint en PointerSensor
const sensors = useSensors(
  useSensor(PointerSensor, {
    activationConstraint: { 
      distance: 8  // 8px de movimiento para iniciar drag
    }
  })
);

// O: Drag handle específico ( GripVertical icon )
```

---

## 7️⃣ Estrategia de Implementación Recomendada

### Fase 1: DnD Básico (Mover entre buses)

**Objetivo:** Permitir mover rutas de un bus a otro, sin reordenamiento visual.

**Cambios:**
1. Envolver Timeline con `DragAndDropProvider`
2. Convertir `RouteBlock` a componente draggable (solo para "levantar")
3. Hacer cada fila de bus (`div` línea 52-89) droppable
4. Implementar `handleScheduleChange` para mover items entre buses

**Dificultad:** 🟢 Baja

### Fase 2: Reordenamiento Visual

**Objetivo:** Permitir reordenar rutas dentro del mismo bus.

**Cambios:**
1. Añadir drop zones invisibles entre RouteBlocks
2. Detectar posición de drop (antes/después de qué ruta)
3. Actualizar array `items` con nuevo orden

**Dificultad:** 🟡 Media

### Fase 3: Drag Horizontal (Avanzado)

**Objetivo:** Arrastrar horizontalmente para cambiar horario.

**Cambios:**
1. Detectar posición X del drop
2. Calcular nueva hora de inicio basada en posición
3. Validar solapamientos
4. Actualizar `start_time` y `end_time`

**Dificultad:** 🔴 Alta

---

## 8️⃣ API Props Necesarios

### TimelineZoomable Modificado

```typescript
interface TimelineZoomableProps {
  schedule: BusSchedule[];
  selectedBusId: string | null;
  onBusSelect: (busId: string) => void;
  
  // NUEVO: Para DnD
  onScheduleChange?: (newSchedule: BusSchedule[]) => void;
  readOnly?: boolean;
}
```

### DragAndDropProvider (ya existe)

```typescript
interface DragAndDropProviderProps {
  schedule: BusSchedule[];
  onScheduleChange: (newSchedule: BusSchedule[]) => void;
  children: React.ReactNode;
}
```

---

## 9️⃣ Archivos a Crear/Modificar

### ✅ Reutilizar Existentes
- `frontend/src/context/DragAndDropContext.jsx` - Ya implementado
- `frontend/src/components/dnd/SortableRoute.jsx` - Referencia
- `frontend/src/components/dnd/BusColumn.jsx` - Referencia

### 📝 Modificar
- `frontend/src/components/TimelineZoomable.jsx` - Agregar Provider
- `frontend/src/components/Timeline.jsx` - Integrar DnD components

### 🆕 Crear
- `frontend/src/components/timeline/DraggableRouteBlock.jsx` - RouteBlock sortable
- `frontend/src/components/timeline/TimelineDropZone.jsx` - Drop zone entre bloques
- `frontend/src/hooks/useTimelineDnD.js` - Lógica de DnD específica (opcional)

---

## 🔟 Checklist de Implementación

- [ ] Entender flujo completo de datos ✅
- [ ] Identificar componente exacto para hacer draggable → **RouteBlock**
- [ ] Identificar dónde poner drop zones → **Área de rutas de cada bus**
- [ ] Documentar dependencias → **@dnd-kit/core, @dnd-kit/sortable**
- [ ] Decidir estrategia: **Fase 1 (mover entre buses)** recomendada
- [ ] Implementar DragAndDropProvider wrapper
- [ ] Crear DraggableRouteBlock con useSortable
- [ ] Hacer filas de bus droppables
- [ ] Conectar onScheduleChange para persistir cambios
- [ ] Probar con zoom y scroll

---

## 📚 Referencias

- `@dnd-kit` documentation: https://docs.dndkit.com/
- Implementación existente: `DraggableSchedule.jsx` + `DragAndDropContext.jsx`
- Componente de referencia: `SortableRoute.jsx`
