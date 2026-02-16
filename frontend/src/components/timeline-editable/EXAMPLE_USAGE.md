# Ejemplo de Uso - Timeline Editable con Drop Zones por Hora

## Componente Principal

```jsx
import { BusRow } from './components/timeline-editable';
import { DndContext } from '@dnd-kit/core';

function EditableTimeline({ buses, hourRange }) {
  const handleDragEnd = (event) => {
    const { active, over } = event;
    
    if (!over) return;
    
    // La drop zone proporciona datos de hora y bus
    const { hour, busId, type } = over.data.current;
    
    if (type === 'hour-zone') {
      // Asignar ruta a esta hora específica
      console.log(`Ruta ${active.id} soltada en Bus ${busId}, hora ${hour}:00`);
    }
  };

  return (
    <DndContext onDragEnd={handleDragEnd}>
      <div className="space-y-2 overflow-x-auto">
        {buses.map(bus => (
          <BusRow
            key={bus.busId}
            bus={bus}
            hourRange={hourRange} // { start: 5, end: 23 }
            onLockAllRoutes={(busId, locked) => {
              console.log(`Bus ${busId} ${locked ? 'bloqueado' : 'desbloqueado'}`);
            }}
            onClearBus={(busId) => {
              console.log(`Limpiar bus ${busId}`);
            }}
          />
        ))}
      </div>
    </DndContext>
  );
}
```

## Estructura de Datos Esperada

```javascript
const buses = [
  {
    busId: "BUS-001",
    routes: [
      {
        route_id: "R-101",
        currentStartTime: "08:00",
        currentEndTime: "10:30"
      },
      {
        route_id: "R-102",
        currentStartTime: "14:00",
        currentEndTime: "16:00"
      }
    ]
  }
];

const hourRange = { start: 5, end: 23 }; // Horario de 5:00 a 23:00
```

## Características Implementadas

✅ Cada hora es una zona de drop independiente (`id: drop-${busId}-${hour}`)
✅ Al pasar por encima, resalta visualmente (verde = puede soltar, rojo = no puede)
✅ Muestra hora en cada zona (05:00, 06:00, etc)
✅ Las rutas se posicionan en su hora correspondiente usando `getRoutesInHour`
✅ Líneas verticales separan las horas (componente `HourLine`)
✅ Scroll horizontal automático si hay muchas horas (`overflow-hidden` + `min-w-0`)

## Estructura de Carpetas

```
timeline-editable/
├── drag-drop/
│   ├── HourDropZone.jsx    # Zona de drop por hora
│   └── index.js
├── bus-row/
│   ├── BusTimelineTrack.jsx # Track con líneas y drop zones
│   ├── BusRow.jsx          # Fila completa del bus
│   └── index.js
├── shared/
│   ├── utils.js            # Funciones auxiliares
│   ├── RouteBlock.jsx      # Bloque de ruta visual
│   ├── HourLine.jsx        # Línea separadora de horas
│   ├── BusLabel.jsx        # Etiqueta del bus
│   ├── BusControls.jsx     # Controles de bloqueo/limpieza
│   └── index.js
├── index.js                # Exportaciones principales
└── EXAMPLE_USAGE.md        # Este archivo
```
