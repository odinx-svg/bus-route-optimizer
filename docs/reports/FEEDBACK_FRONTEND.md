# 📋 FEEDBACK AGENT FRONTEND LEAD

**Agente:** Frontend Lead  
**Fase actual:** 4 - Frontend Robusto  
**Fecha inicio:** 2026-02-10  
**Estado:** 🚀 **INICIANDO**

---

## 🎯 TAREAS ASIGNADAS

| # | Tarea | Duración | Prioridad |
|---|-------|----------|-----------|
| 4.1 | Toast notifications | 1 día | Alta |
| 4.2 | Progreso WebSocket | 2 días | Alta |
| 4.3 | Drag & drop | 3 días | Media |
| 4.4 | Timeline | 3 días | Media |
| 4.5 | Compare view | 2 días | Baja |
| 4.6 | Tests E2E | 2 días | Media |

**Total estimado:** 13 días (~2 semanas)

---

## 📋 CONTEXTO DEL SISTEMA

### Backend listo (Fases 1-3 completadas)
- ✅ PostgreSQL + API REST
- ✅ Celery + Redis + WebSockets
- ✅ Optimización multi-objetivo + LNS
- ✅ Endpoints: `/optimize-async`, `/jobs/{id}`, `/ws/optimize/{id}`

### Frontend actual (React + Vite + Tailwind)
```
frontend/src/
  components/
    FileUpload.jsx
    MapView.jsx
    Sidebar.jsx
    BusListPanel.jsx
  services/
    api.service.ts
  App.jsx
```

### Stack tecnológico
- React 18
- Vite
- Tailwind CSS
- TypeScript (parcial)
- Leaflet (mapas)

---

## 📝 ESPECIFICACIONES DE TAREAS

### Tarea 4.1: Toast Notifications

**Objetivo:** Reemplazar todos los `alert()` nativos por notificaciones modernas.

**Implementación sugerida:**
```bash
npm install sonner
```

```typescript
// frontend/src/services/notifications.ts
import { toast } from 'sonner';

export const notifications = {
  success: (message: string, description?: string) => {
    toast.success(message, { description });
  },
  
  error: (message: string, description?: string) => {
    toast.error(message, { description });
  },
  
  info: (message: string, description?: string) => {
    toast.info(message, { description });
  },
  
  promise: <T>(
    promise: Promise<T>,
    messages: {
      loading: string;
      success: string;
      error: string;
    }
  ) => {
    return toast.promise(promise, messages);
  }
};

// Uso en componentes
notifications.success(
  'Optimización completada',
  '8 buses asignados para el lunes'
);

notifications.error(
  'Error de conexión',
  'Revisa que el backend esté activo'
);
```

**Reemplazar en:**
- `App.jsx` - Todos los `alert()`
- `FileUpload.jsx` - Errores de upload
- `Sidebar.jsx` - Errores de optimización

---

### Tarea 4.2: Progreso WebSocket

**Objetivo:** Mostrar progreso en tiempo real durante la optimización.

**Protocolo WebSocket (de Agent Backend):**
```typescript
// Conectar a ws://localhost:8000/ws/optimize/{job_id}

// Mensajes del servidor:
interface WebSocketMessage {
  type: 'progress' | 'status' | 'completed' | 'error' | 'pong';
  job_id: string;
  phase?: string;        // 'starting', 'building_chains', etc.
  progress?: number;     // 0-100
  message?: string;
  result?: any;          // Cuando completed
  error_code?: string;   // Cuando error
}
```

**Implementación sugerida:**
```typescript
// frontend/src/hooks/useOptimizationProgress.ts
import { useState, useEffect, useRef } from 'react';

export function useOptimizationProgress(jobId: string | null) {
  const [progress, setProgress] = useState(0);
  const [phase, setPhase] = useState('');
  const [status, setStatus] = useState<'idle' | 'running' | 'completed' | 'error'>('idle');
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const wsUrl = `${import.meta.env.VITE_WS_URL}/ws/optimize/${jobId}`;
    ws.current = new WebSocket(wsUrl);

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'progress':
          setProgress(data.progress);
          setPhase(data.phase);
          break;
        case 'status':
          setStatus(data.status);
          break;
        case 'completed':
          setStatus('completed');
          setProgress(100);
          break;
        case 'error':
          setStatus('error');
          break;
      }
    };

    ws.current.onerror = () => {
      setStatus('error');
    };

    return () => {
      ws.current?.close();
    };
  }, [jobId]);

  return { progress, phase, status };
}
```

**Componente de progreso:**
```tsx
// frontend/src/components/OptimizationProgress.tsx
import { useOptimizationProgress } from '../hooks/useOptimizationProgress';

export function OptimizationProgress({ jobId }: { jobId: string }) {
  const { progress, phase, status } = useOptimizationProgress(jobId);

  const phases: Record<string, string> = {
    starting: 'Iniciando...',
    preprocessing: 'Preprocesando rutas...',
    building_chains: 'Construyendo cadenas...',
    matching_blocks: 'Emparejando bloques...',
    local_search: 'Optimizando...',
    finalizing: 'Finalizando...',
    completed: '¡Completado!'
  };

  return (
    <div className="w-full max-w-md p-4 bg-white rounded-lg shadow">
      <div className="flex justify-between mb-2">
        <span className="text-sm font-medium">
          {phases[phase] || 'Procesando...'}
        </span>
        <span className="text-sm text-gray-500">{progress}%</span>
      </div>
      
      <div className="w-full bg-gray-200 rounded-full h-2.5">
        <div
          className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>
      
      {status === 'error' && (
        <p className="mt-2 text-sm text-red-600">
          Error en la optimización
        </p>
      )}
    </div>
  );
}
```

---

### Tarea 4.3: Drag & Drop

**Objetivo:** Permitir mover rutas entre buses visualmente.

**Librería sugerida:**
```bash
npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities
```

**Implementación:**
```tsx
// frontend/src/components/BusListDnd.tsx
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable
} from '@dnd-kit/sortable';

// Componente para cada ruta arrastrable
function SortableRoute({ route, busId }: { route: Route; busId: string }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({
    id: `${busId}-${route.id}`,
    data: { route, busId }
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className="p-2 bg-white border rounded cursor-move hover:shadow"
    >
      {route.name}
    </div>
  );
}

// Componente principal
export function BusListDnd({ schedule, onReorder }: Props) {
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates
    })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    
    if (!over || active.id === over.id) return;

    // Lógica de reordenamiento
    const activeData = active.data.current;
    const overData = over.data.current;

    if (activeData.busId !== overData.busId) {
      // Mover entre buses
      onReorder({
        routeId: activeData.route.id,
        fromBusId: activeData.busId,
        toBusId: overData.busId
      });
    }
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      {schedule.map((bus) => (
        <div key={bus.bus_id} className="mb-4">
          <h3>Bus {bus.bus_id}</h3>
          <SortableContext items={bus.items.map(i => `${bus.bus_id}-${i.route_id}`)}>
            {bus.items.map((item) => (
              <SortableRoute
                key={item.route_id}
                route={item}
                busId={bus.bus_id}
              />
            ))}
          </SortableContext>
        </div>
      ))}
    </DndContext>
  );
}
```

---

### Tarea 4.4: Timeline

**Objetivo:** Visualización temporal de horarios de buses.

**Implementación sugerida:**
```tsx
// frontend/src/components/Timeline.tsx
import { useMemo } from 'react';

interface TimelineProps {
  schedule: BusSchedule[];
  hourRange: [number, number]; // [6, 22]
}

export function Timeline({ schedule, hourRange = [6, 22] }: TimelineProps) {
  const hours = useMemo(() => {
    const range = [];
    for (let h = hourRange[0]; h <= hourRange[1]; h++) {
      range.push(h);
    }
    return range;
  }, [hourRange]);

  return (
    <div className="overflow-x-auto">
      <div className="min-w-max">
        {/* Header con horas */}
        <div className="flex border-b">
          <div className="w-20 p-2 font-medium">Bus</div>
          {hours.map((h) => (
            <div key={h} className="w-16 p-2 text-center text-sm">
              {h}:00
            </div>
          ))}
        </div>

        {/* Filas por bus */}
        {schedule.map((bus) => (
          <div key={bus.bus_id} className="flex border-b hover:bg-gray-50">
            <div className="w-20 p-2 font-medium">{bus.bus_id}</div>
            <div className="relative flex-1 h-12">
              {bus.items.map((item) => {
                const start = timeToMinutes(item.start_time);
                const end = timeToMinutes(item.end_time);
                const left = ((start / 60) - hourRange[0]) * 64; // 64px por hora
                const width = ((end - start) / 60) * 64;

                return (
                  <div
                    key={item.route_id}
                    className={`absolute h-8 rounded text-xs flex items-center px-2 ${
                      item.type === 'entry' ? 'bg-blue-500' : 'bg-green-500'
                    }`}
                    style={{ left, width }}
                    title={`${item.route_id}: ${item.start_time} - ${item.end_time}`}
                  >
                    {item.route_id}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function timeToMinutes(time: string): number {
  const [h, m] = time.split(':').map(Number);
  return h * 60 + m;
}
```

---

## 📝 LOG DE TRABAJO

### 2026-02-10 - Inicio de Fase 4

**Planificación inicial:**
1. Toast notifications primero (rápido, alto impacto UX)
2. WebSocket progreso (integra Fase 2)
3. Drag & drop (feature diferenciador)
4. Timeline (visualización avanzada)
5. Compare view (opcional, baja prioridad)
6. Tests E2E (Playwright)

**Dependencias:**
- Backend WebSocket endpoint (✅ listo)
- API endpoints async (✅ listo)
- Componentes existentes (✅ listos)

**Preguntas para Kimi Lead:**
- ¿Prioridad de compare view? (Sugerencia: postergar a Fase 5 si presión de tiempo)
- ¿Tests E2E con Playwright o Cypress? (Sugerencia: Playwright)

---

## 📊 MÉTRICAS DEL TRABAJO

| Métrica | Valor |
|---------|-------|
| Tareas asignadas | 6 |
| Tiempo estimado total | 13 días |
| Tiempo transcurrido | 0 días |
| Bloqueos | 0 |
| Dependencias pendientes | 0 (Backend listo) |

---

## 🔄 COMUNICACIÓN CON OTROS AGENTES

### Con Kimi Lead
**Tema:** Prioridades y alcance  
**Estado:** ⏳ Esperando confirmación

### Con Agent Backend
**Tema:** WebSocket protocol details  
**Estado:** ✅ Documentación recibida en FEEDBACK_BACKEND.md

### Con Agent Testing
**Tema:** Tests E2E coordinación  
**Estado:** 📋 Planificar al final de Fase 4

---

## 📅 PRÓXIMOS PASOS

1. [ ] Instalar sonner y configurar toast notifications
2. [ ] Reemplazar alert() en App.jsx
3. [ ] Implementar hook useOptimizationProgress
4. [ ] Crear componente OptimizationProgress
5. [ ] Integrar con Sidebar/optimización
6. [ ] Testear WebSocket flujo completo
7. [ ] Documentar progreso en este archivo

---

**Última actualización:** 2026-02-10 - Inicio de tarea  
**Próxima actualización:** Al completar Toast notifications (1 día)
