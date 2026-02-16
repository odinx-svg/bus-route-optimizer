# Timeline Editable - Documento de Arquitectura

## 📋 Resumen Ejecutivo

El **Timeline Editable** es un sistema avanzado de gestión visual de horarios de buses que permite manipular rutas como "piezas de lego" en una interfaz tipo timeline. Este documento describe la arquitectura completa del sistema.

### Funcionalidades Principales

| Funcionalidad | Descripción | Estado |
|--------------|-------------|--------|
| RouteBlock con Candado | Bloqueo de rutas para prevenir modificaciones | ✅ Diseñado |
| Validación OSRM | Verificación de compatibilidad geográfica/temporal | ✅ Diseñado |
| Rutas Libres | Gestión de rutas no asignadas a ningún bus | ✅ Diseñado |
| Posicionamiento por Hora | Colocación exacta en el timeline por hora | ✅ Diseñado |
| Sugerencias Inteligentes | Recomendaciones de ubicación optimizadas | ✅ Diseñado |

---

## 🏗️ Arquitectura de Componentes

```
timeline-editable/
├── ARCHITECTURE.md                  # Este documento
├── 
├── components/                      # Componentes React
│   ├── TimelineEditable.tsx         # Componente principal (orquestador)
│   ├── TimelineEditableProvider.tsx # Provider de contexto
│   │
│   ├── layout/                      # Estructura de layout
│   │   ├── TimelineHeader.tsx       # Cabecera con horas y controles
│   │   ├── TimelineContainer.tsx    # Contenedor principal
│   │   └── TimelineGrid.tsx         # Grid de horas de fondo
│   │
│   ├── bus-row/                     # Fila de bus
│   │   ├── BusTimelineRow.tsx       # Fila completa de un bus
│   │   ├── BusLabel.tsx             # Etiqueta del bus (B001)
│   │   ├── BusHeader.tsx            # Cabecera con controles del bus
│   │   └── BusTrack.tsx             # Área de drop de rutas
│   │
│   ├── route-block/                 # Bloque de ruta (pieza de lego)
│   │   ├── RouteBlock.tsx           # Componente principal
│   │   ├── RouteBlockContent.tsx    # Contenido interno
│   │   ├── LockButton.tsx           # Botón de candado
│   │   ├── TimeRangeDisplay.tsx     # Display de horas
│   │   ├── RouteInfo.tsx            # Info de origen/destino
│   │   ├── CompatibilityBadge.tsx   # Badge verde/amarillo/rojo
│   │   └── RouteBlockDragOverlay.tsx # Vista previa al arrastrar
│   │
│   ├── unassigned-panel/            # Panel de rutas libres
│   │   ├── UnassignedRoutesPanel.tsx # Panel lateral
│   │   ├── UnassignedRouteCard.tsx  # Tarjeta de ruta libre
│   │   ├── CollapseButton.tsx       # Botón colapsar panel
│   │   └── EmptyState.tsx           # Estado vacío
│   │
│   ├── suggestions/                 # Sistema de sugerencias
│   │   ├── SuggestionList.tsx       # Lista de sugerencias
│   │   ├── SuggestionCard.tsx       # Card individual
│   │   ├── SuggestionScore.tsx      # Visualización de score
│   │   └── SuggestionReasons.tsx    # Razones de la sugerencia
│   │
│   ├── drag-drop/                   # Sistema DnD
│   │   ├── DragOverlay.tsx          # Capa de arrastre global
│   │   ├── DropZone.tsx             # Zona de drop genérica
│   │   ├── HourDropZone.tsx         # Zona de drop por hora
│   │   └── useDragAndDrop.ts        # Hook de DnD
│   │
│   ├── validation/                  # Validación
│   │   ├── ValidationOverlay.tsx    # Overlay de errores
│   │   ├── ValidationBadge.tsx      # Badge de estado
│   │   ├── ErrorList.tsx            # Lista de errores
│   │   └── CompatibilityIndicator.tsx # Indicador visual
│   │
│   └── controls/                    # Controles
│       ├── ZoomControls.tsx         # Controles de zoom
│       ├── HourRangeSelector.tsx    # Selector de rango
│       ├── SnapToggle.tsx           # Toggle snap-to-grid
│       └── ViewOptions.tsx          # Opciones de vista
│
├── hooks/                           # Hooks personalizados
│   ├── useTimelineEditable.ts       # Hook principal del store
│   ├── useRoutePosition.ts          # Cálculo de posición visual
│   ├── useCompatibilityCheck.ts     # Verificación de compatibilidad
│   ├── useSuggestions.ts            # Generación de sugerencias
│   ├── useValidation.ts             # Validación de estado
│   └── useKeyboardShortcuts.ts      # Atajos de teclado
│
├── utils/                           # Utilidades
│   ├── timeCalculations.ts          # Cálculos de tiempo
│   ├── positionCalculations.ts      # Cálculos de posición
│   ├── osrmClient.ts                # Cliente OSRM
│   ├── suggestionEngine.ts          # Motor de sugerencias
│   └── validators.ts                # Validadores
│
└── styles/                          # Estilos
    ├── timeline.css                 # Estilos base
    ├── route-block.css              # Estilos de bloques
    ├── variables.css                # Variables CSS
    └── themes/                      # Temas
        ├── light.css
        └── dark.css
```

---

## 📊 Modelo de Datos

### Diagrama de Clases

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TimelineEditableState                           │
├─────────────────────────────────────────────────────────────────────────┤
│ buses: TimelineBus[]                                                    │
│ unassignedRoutes: ExtendedRouteItem[]                                   │
│ viewConfig: TimelineViewConfig                                          │
│ validation: TimelineValidationState                                     │
│ dragState: DragState                                                    │
│ activeSuggestions: RouteSuggestion[]                                    │
│ osrmCache: Map<string, CompatibilityCheck>                              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
          ▼                         ▼                         ▼
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│    TimelineBus      │   │ ExtendedRouteItem   │   │   RouteSuggestion   │
├─────────────────────┤   ├─────────────────────┤   ├─────────────────────┤
│ busId: string       │   │ route_id: string    │   │ routeId: string     │
│ busName: string     │   │ route_code: string  │   │ suggestedPosition   │
│ color: string       │   │ start_time: string  │   │ score: number       │
│ routes: []          │◄──│ end_time: string    │   │ reasons: []         │
│ isCollapsed: bool   │   │ isLocked: boolean   │   │ isApplicable: bool  │
│ isVisible: bool     │   │ isEditable: boolean │   └─────────────────────┘
└─────────────────────┘   │ status: RouteStatus │
                          │ assignedBusId?: str │
                          │ compatibility?: {}  │
                          └─────────────────────┘
```

### Flujo de Datos

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   API/Data   │────►│  Transform   │────►│    Store     │
│   (Routes)   │     │   Adapter    │     │   (Zustand)  │
└──────────────┘     └──────────────┘     └──────────────┘
                                                   │
                         ┌─────────────────────────┼─────────────────────────┐
                         │                         │                         │
                         ▼                         ▼                         ▼
                   ┌──────────┐             ┌──────────┐             ┌──────────┐
                   │ BusRows  │             │Unassigned│             │Validation│
                   │ (Visual) │             │  Panel   │             │  Engine  │
                   └──────────┘             └──────────┘             └──────────┘
```

---

## 🎯 Componentes Detallados

### 1. TimelineEditable (Componente Principal)

```typescript
interface TimelineEditableProps {
  initialBuses?: TimelineBus[];
  initialUnassignedRoutes?: ExtendedRouteItem[];
  onStateChange?: (state: TimelineEditableState) => void;
  onValidationError?: (errors: ValidationError[]) => void;
}
```

**Responsabilidades:**
- Inicializar el store con datos
- Orquestar los componentes hijos
- Gestionar el contexto global
- Escuchar cambios y propagar eventos

### 2. BusTimelineRow

```typescript
interface BusTimelineRowProps {
  bus: TimelineBus;
  isActive?: boolean;
  onRouteClick?: (route: ExtendedRouteItem) => void;
}
```

**Responsabilidades:**
- Renderizar la etiqueta del bus
- Contener el track de rutas
- Gestionar colapsado/expandido
- Ser un droppable para rutas

### 3. RouteBlock (Pieza de Lego)

```typescript
interface RouteBlockProps {
  route: ExtendedRouteItem;
  busId?: string;
  isDragging?: boolean;
  onLockToggle?: (routeId: string) => void;
}
```

**Responsabilidades:**
- Mostrar información de la ruta
- Gestionar estado de bloqueo (candado)
- Permitir drag & drop
- Mostrar indicadores de compatibilidad
- Calcular posición visual basada en hora

**Estados Visuales:**

| Estado | Visual | Descripción |
|--------|--------|-------------|
| Normal | Fondo color, borde sutil | Estado por defecto |
| Locked | Icono candado 🔒, opacidad reducida | No editable |
| Dragging | Elevado, opacidad alta | Siendo arrastrado |
| Conflicto | Borde rojo, badge warning | Tiene errores |
| Compatible | Badge verde ✅ | Compatible con vecinos |
| Incompatible | Badge rojo ❌ | Incompatible |
| Selected | Borde destacado | Seleccionado |

### 4. UnassignedRoutesPanel

**Responsabilidades:**
- Listar rutas no asignadas
- Permitir arrastrar rutas a buses
- Mostrar sugerencias de asignación
- Colapsar/expandir

### 5. SuggestionList

**Responsabilidades:**
- Mostrar sugerencias ordenadas por score
- Permitir aplicar sugerencia con un click
- Explicar razones de cada sugerencia
- Actualizar en tiempo real

---

## 🔒 Sistema de Candado (Lock System)

### Estados de Edición

```typescript
interface RouteEditControl {
  isEditable: boolean;  // Puede editarse (default: true)
  isLocked: boolean;    // Bloqueada (default: false)
  lockReason?: string;  // Razón del bloqueo
}
```

### Reglas de Negocio

| isEditable | isLocked | Comportamiento |
|------------|----------|----------------|
| true | false | ✅ Edición completa permitida |
| true | true | ❌ Solo visualización, candado cerrado |
| false | false | ❌ Solo visualización |
| false | true | ❌ Solo visualización |

### Flujo de Bloqueo

```
Usuario clicka candado
        │
        ▼
┌───────────────┐
│  Confirmar?   │◄── Si hay dependencias
│  (Modal)      │
└───────────────┘
        │
        ▼
┌───────────────┐
│  Actualizar   │
│  isLocked     │
└───────────────┘
        │
        ▼
┌───────────────┐
│  Revalidar    │
│  afectados    │
└───────────────┘
```

---

## 🗺️ Validación OSRM

### Cálculo de Compatibilidad

```typescript
interface CompatibilityCheck {
  routeId: string;
  travelTimeMinutes: number;     // Tiempo OSRM
  bufferMinutes: number;         // Buffer seguridad (10min)
  totalRequiredMinutes: number;  // Suma requerida
  isCompatible: boolean;         // Resultado
  compatibilityScore: number;    // 0-100
}
```

### Algoritmo

```
┌─────────────────┐
│  Ruta A termina │
│  en coords X    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Ruta B inicia  │
│  en coords Y    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Consultar      │────►│  Cache OSRM?    │
│  OSRM           │     │                 │
└─────────────────┘     └────────┬────────┘
                                 │
                    ┌────────────┴────────────┐
                    │ Sí                      │ No
                    ▼                         ▼
           ┌─────────────┐           ┌─────────────────┐
           │ Usar cache  │           │ Llamar API OSRM │
           └──────┬──────┘           │ Calcular ruta   │
                  │                  └────────┬────────┘
                  │                           │
                  └────────────┬──────────────┘
                               ▼
                    ┌─────────────────────┐
                    │  Calcular tiempos   │
                    │  - travelTime       │
                    │  - buffer           │
                    │  - availableTime    │
                    └──────────┬──────────┘
                               ▼
                    ┌─────────────────────┐
                    │  Comparar:          │
                    │  available >= req?  │
                    └──────────┬──────────┘
                               │
                    ┌──────────┴──────────┐
                    │ Sí                  │ No
                    ▼                     ▼
           ┌─────────────┐      ┌─────────────────┐
           │ Compatible  │      │ Incompatible    │
           │ Score: 100  │      │ Score: < 100    │
           └─────────────┘      └─────────────────┘
```

### Cache OSRM

```typescript
type OSRMCacheKey = `${string}_end_${string}_start`;

// Ejemplo: "route_123_end_route_456_start"
```

**Estrategia de Cache:**
- TTL: 1 hora
- LRU: Máximo 1000 entradas
- Persistencia: localStorage (opcional)

---

## 💡 Motor de Sugerencias

### Factores de Puntuación

| Factor | Peso | Descripción |
|--------|------|-------------|
| Buffer de tiempo | 40% | Tiempo disponible entre rutas |
| Cercanía geográfica | 30% | Distancia entre destino/origen |
| Secuencia lógica | 20% | Tipo de ruta (entry/exit) |
| Optimización global | 10% | Impacto en otros buses |

### Algoritmo de Sugerencias

```typescript
function generateSuggestions(routeId: string): RouteSuggestion[] {
  const route = getRoute(routeId);
  const suggestions: RouteSuggestion[] = [];
  
  // Para cada bus
  buses.forEach(bus => {
    // Para cada posible posición
    for (let i = 0; i <= bus.routes.length; i++) {
      const score = calculateScore(route, bus, i);
      
      if (score >= MIN_SUGGESTION_SCORE) {
        suggestions.push({
          routeId,
          suggestedPosition: { busId: bus.busId, index: i, ... },
          score,
          reasons: generateReasons(route, bus, i),
          isApplicable: checkApplicability(route, bus, i),
        });
      }
    }
  });
  
  return suggestions.sort((a, b) => b.score - a.score);
}
```

---

## 🎨 Sistema de Posicionamiento Visual

### Cálculo de Left/Width

```typescript
function calculateRoutePosition(
  route: ExtendedRouteItem,
  viewConfig: TimelineViewConfig
): { left: number; width: number } {
  const { hourRange, pixelsPerHour } = viewConfig;
  
  const rangeStart = hourRange[0] * 60;  // minutos
  const rangeEnd = hourRange[1] * 60;
  const rangeDuration = rangeEnd - rangeStart;
  
  const routeStart = timeToMinutes(route.currentStartTime);
  const routeEnd = timeToMinutes(route.currentEndTime);
  const routeDuration = routeEnd - routeStart;
  
  const totalPixels = (rangeDuration / 60) * pixelsPerHour;
  
  const left = ((routeStart - rangeStart) / rangeDuration) * totalPixels;
  const width = (routeDuration / 60) * pixelsPerHour;
  
  return { left, width };
}
```

### Grid de Horas

```
6:00    7:00    8:00    9:00    10:00   11:00
│       │       │       │       │       │
├───────┼───────┼───────┼───────┼───────┤  ◄── Grid líneas
│   ┌───────────┐   ┌───┐               │
│   │   Ruta A  │   │ B │               │  ◄── RouteBlocks
│   └───────────┘   └───┘               │
│                                       │
```

---

## 🔄 Integración con Sistema Existente

### Adaptador de Datos

```typescript
// Transformar schedule actual → ExtendedRouteItem[]
function transformScheduleToEditable(
  schedule: BusSchedule[],
  originalRoutes: Route[]
): { buses: TimelineBus[]; unassigned: ExtendedRouteItem[] } {
  const buses: TimelineBus[] = schedule.map((bus, index) => ({
    busId: bus.bus_id || generateId(),
    busName: bus.bus_name || `Bus ${index + 1}`,
    color: getBusColor(index),
    isCollapsed: false,
    isVisible: true,
    routes: bus.routes.map((route, rIndex) => ({
      // Datos base
      ...route,
      // Control de edición
      isEditable: true,
      isLocked: false,
      originalBusId: bus.bus_id,
      // Datos geográficos
      startCoordinates: findCoordinates(originalRoutes, route.route_id, 'start'),
      endCoordinates: findCoordinates(originalRoutes, route.route_id, 'end'),
      origin: findStopName(originalRoutes, route.route_id, 'start'),
      destination: findStopName(originalRoutes, route.route_id, 'end'),
      // Estado
      status: 'assigned',
      assignedBusId: bus.bus_id,
      positionInBus: rIndex,
      currentStartTime: route.start_time,
      currentEndTime: route.end_time,
    })),
  }));
  
  return { buses, unassigned: [] };
}
```

### API de Integración

```typescript
// Hook de integración
function useTimelineEditableIntegration() {
  const { data: schedule } = useOptimizedSchedule();
  const { data: routes } = useRoutes();
  const initialize = useTimelineEditableStore(state => state.initialize);
  
  useEffect(() => {
    if (schedule && routes) {
      const { buses, unassigned } = transformScheduleToEditable(schedule, routes);
      initialize(buses, unassigned);
    }
  }, [schedule, routes]);
}
```

---

## 📱 Flujos de Usuario

### Flujo 1: Bloquear una Ruta

```
┌─────────────┐
│  Ver ruta   │
│  en timeline│
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Click en    │
│ candado 🔓  │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────────┐
│ ¿Dependencias?├───►│ Modal confirmar │
│   (rutas    │ Sí  │ - Rutas afectadas
│    después) │     │ - Cambios       │
└──────┬──────┘     └─────────────────┘
       │ No
       ▼
┌─────────────┐
│ isLocked =  │
│    true     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Mostrar 🔒  │
│ Visual      │
└─────────────┘
```

### Flujo 2: Mover Ruta con Validación

```
┌─────────────────┐
│ Drag inicia     │
│ desde Bus A     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Calcular        │
│ posibles targets│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Hover sobre     │
│ Bus B, hora X   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Validar:        │
│ - ¿Hay espacio? │
│ - ¿Compatible?  │
│ - ¿Sin conflictos?
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────┐ ┌────────┐
│Válido  │ │Inválido│
│Highlight│ │  (red) │
│(green) │ │        │
└───┬───┘ └────┬───┘
    │          │
    ▼          ▼
┌─────────────────┐
│ Drop válido:    │
│ Ejecutar movimiento
│ Actualizar estado
│ Revalidar       │
└─────────────────┘
```

### Flujo 3: Aplicar Sugerencia

```
┌─────────────────┐
│ Rutas libres    │
│ disponibles     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Click en ruta   │
│ (selección)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Motor calcula   │
│ sugerencias     │
│ (automático)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Mostrar lista   │
│ ordenada        │
│ - Score         │
│ - Razones       │
│ - Preview       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Usuario clicka  │
│ sugerencia      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Aplicar cambio  │
│ - Mover ruta    │
│ - Actualizar UI │
│ - Recalcular    │
│   sugerencias   │
└─────────────────┘
```

---

## 🧪 Testing

### Estrategia de Tests

| Tipo | Cobertura | Herramientas |
|------|-----------|--------------|
| Unit Tests | Store, utils | Vitest |
| Component Tests | UI components | React Testing Library |
| Integration | DnD, validación | Playwright |
| E2E | Flujos completos | Playwright |

### Tests Críticos

```typescript
// Store tests
describe('TimelineEditableStore', () => {
  it('should lock a route', () => {
    const store = createTestStore();
    store.lockRoute('route-1');
    expect(store.getRoute('route-1')?.isLocked).toBe(true);
  });
  
  it('should not move locked route', () => {
    const store = createTestStore();
    store.lockRoute('route-1');
    const result = store.moveRoute('route-1', 'bus-2');
    expect(result).toBe(false);
  });
  
  it('should validate time conflicts', () => {
    const store = createTestStoreWithOverlap();
    store.validateAll();
    expect(store.validation.errors).toHaveLength(1);
  });
});
```

---

## 📈 Rendimiento

### Optimizaciones

| Área | Estrategia | Implementación |
|------|------------|----------------|
| Render | Virtualización | react-window para listas largas |
| Cálculos | Memoización | useMemo para posiciones |
| Validación | Debounce | 300ms delay en validación |
| OSRM | Cache agresivo | Map en memoria + localStorage |
| Sugerencias | Web Worker | Cálculo en segundo plano |
| Selección | Optimistic UI | Actualización inmediata, rollback si falla |

### Métricas Objetivo

| Métrica | Objetivo | Máximo |
|---------|----------|--------|
| Time to Interactive | < 2s | 3s |
| FPS durante drag | 60fps | 30fps |
| Validación | < 500ms | 1s |
| Sugerencias | < 1s | 2s |
| Memoria | < 100MB | 200MB |

---

## 🔮 Roadmap

### Fase 1: MVP (Semana 1-2)
- [x] Modelo de datos
- [x] Store básico
- [ ] RouteBlock con drag & drop
- [ ] Visualización básica

### Fase 2: Edición (Semana 3-4)
- [ ] Sistema de candado
- [ ] Movimiento entre buses
- [ ] Cambio de hora

### Fase 3: Validación (Semana 5-6)
- [ ] Integración OSRM
- [ ] Validación de compatibilidad
- [ ] Visualización de errores

### Fase 4: Inteligencia (Semana 7-8)
- [ ] Motor de sugerencias
- [ ] Optimización automática
- [ ] Atajos de teclado

---

## 📚 Referencias

- [Zustand Documentation](https://docs.pmnd.rs/zustand)
- [Dnd Kit](https://dndkit.com/)
- [OSRM API](http://project-osrm.org/docs/v5.24.0/api/)
- [React Performance](https://react.dev/learn/render-and-commit)

---

## 📝 Changelog

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0.0 | 2026-02-11 | Diseño inicial completo |

---

**Autor:** Agent Architect Lead  
**Última Actualización:** 2026-02-11  
**Estado:** ✅ Completado
