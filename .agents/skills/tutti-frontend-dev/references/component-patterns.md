# Patrones de Componentes Frontend

## Timeline Editable Architecture

### Data Flow

```
App.jsx (global state)
    |
    v
OptimizationStudio.jsx
    |
    v
TimelineEditable.jsx
    |
    +---> Workspace.jsx
    |         +---> BusRow[]
    |         |       +---> RouteBlock[]
    |         +---> UnassignedPanel
    |                 +---> DraggableUnassignedRoute[]
    |
    +---> RouteDetailsPanel.jsx
```

### Estados del Sistema

```javascript
// Estado global (Zustand)
{
  routes: Route[],
  scheduleByDay: {
    L: { schedule: BusSchedule[], stats: {}, unassigned_routes: [] },
    M: {...},
    // ...
  },
  activeDay: 'L',
  selectedBusId: null,
  selectedRouteId: null,
  isDirty: false
}
```

### Drag & Drop en Timeline

```javascript
// Tipos de drag:
// 1. Mover ruta entre buses
// 2. Mover ruta a unassigned
// 3. Mover ruta de unassigned a bus
// 4. Reordenar dentro del mismo bus

const handleDragEnd = (event) => {
  const { active, over } = event;
  
  if (!over) return;
  
  const activeData = active.data.current;
  const overData = over.data.current;
  
  // Caso 1: Mover a otro bus
  if (overData.type === 'bus-drop-zone') {
    moveRouteToBus(activeData.routeId, overData.busId);
  }
  
  // Caso 2: Mover a unassigned
  if (overData.type === 'unassigned-zone') {
    moveRouteToUnassigned(activeData.routeId, activeData.busId);
  }
  
  // Caso 3: Reordenar
  if (overData.type === 'route-reorder') {
    reorderRoutes(activeData.routeId, overData.index);
  }
};
```

## Route Block States

```javascript
// Estados visuales de un bloque de ruta
const routeBlockStates = {
  default: 'border-l-4 border-blue-500 bg-[#1a2d3f]',
  selected: 'ring-2 ring-blue-400 border-blue-500',
  conflict: 'border-red-500 bg-red-900/20',
  warning: 'border-amber-500 bg-amber-900/20',
  locked: 'opacity-60 grayscale',
  dragging: 'opacity-50 scale-105 shadow-lg',
};
```

## Bus Row Component

```javascript
const BusRow = ({ 
  bus, 
  isSelected, 
  isPinned,
  onSelect, 
  onTogglePin,
  conflicts = []
}) => {
  return (
    <div 
      className={`
        flex items-center gap-2 p-2 rounded-lg
        ${isSelected ? 'bg-[#253a4f]' : 'hover:bg-[#1a2d3f]'}
      `}
    >
      {/* Bus Label */}
      <BusLabel 
        busId={bus.bus_id}
        isPinned={isPinned}
        onTogglePin={() => onTogglePin(bus.bus_id)}
      />
      
      {/* Timeline Track */}
      <BusTimelineTrack>
        {bus.items.map(item => (
          <RouteBlock
            key={item.route_id}
            item={item}
            hasConflict={conflicts.includes(item.route_id)}
          />
        ))}
      </BusTimelineTrack>
    </div>
  );
};
```

## Custom Hooks Patterns

### useAutoSave

```javascript
const useAutoSave = ({
  workspaceId,
  scheduleByDay,
  isDirty,
  saveInterval = 30000
}) => {
  useEffect(() => {
    if (!workspaceId || !isDirty) return;
    
    const timer = setInterval(async () => {
      await saveWorkspaceVersion(workspaceId, {
        save_kind: 'autosave',
        schedule_by_day: scheduleByDay
      });
    }, saveInterval);
    
    return () => clearInterval(timer);
  }, [workspaceId, isDirty, scheduleByDay, saveInterval]);
};
```

### useKeyboardShortcuts

```javascript
const useKeyboardShortcuts = ({
  onSave,
  onUndo,
  onRedo,
  onDelete
}) => {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        onSave();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        e.preventDefault();
        onUndo();
      }
      // ...
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onSave, onUndo, onRedo, onDelete]);
};
```

## Optimistic Updates

```javascript
// 1. Actualizar UI inmediatamente
const moveRoute = (routeId, targetBusId) => {
  // Optimistic update
  setSchedule(prev => {
    // Mover ruta localmente
    return newSchedule;
  });
  
  // Llamada API
  api.moveRoute(routeId, targetBusId)
    .then(result => {
      // Confirmar con datos reales
      setSchedule(result);
    })
    .catch(err => {
      // Rollback
      setSchedule(originalSchedule);
      notifications.error('Error', err.message);
    });
};
```

## WebSocket Integration

```javascript
const useOptimizationProgress = ({
  jobId,
  onProgress,
  onComplete,
  onError
}) => {
  useEffect(() => {
    if (!jobId) return;
    
    const ws = new WebSocket(`ws://localhost:8000/ws/optimization/${jobId}`);
    
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      
      switch (msg.type) {
        case 'progress':
          onProgress?.(msg);
          break;
        case 'completed':
          onComplete?.(msg.result);
          break;
        case 'error':
          onError?.(msg.error_code, msg.message);
          break;
      }
    };
    
    return () => ws.close();
  }, [jobId, onProgress, onComplete, onError]);
};
```

## PDF Export Flow

```javascript
const handleExportPDF = async () => {
  const loadingId = notifications.loading('Generando PDF...');
  
  try {
    const blob = await apiService.exportPDF(schedule, dayName);
    
    // Desktop: usar API nativa
    if (window.pywebview?.api?.save_pdf_file) {
      const base64 = await blobToBase64(blob);
      const result = await window.pywebview.api.save_pdf_file(base64, filename);
      if (result.success) {
        notifications.success('PDF guardado', result.path);
      }
    } 
    // Web: download normal
    else {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      window.URL.revokeObjectURL(url);
      notifications.success('PDF descargado');
    }
  } catch (err) {
    notifications.error('Error', err.message);
  } finally {
    notifications.dismiss(loadingId);
  }
};
```
