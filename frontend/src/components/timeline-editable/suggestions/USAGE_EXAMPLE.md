# Sistema de Auto-Ordenación "Más Compatible Primero"

Este sistema proporciona sugerencias inteligentes ordenadas por compatibilidad cuando una ruta se libera.

## Componentes

### 1. SmartSuggestionList
Componente principal que muestra la lista de sugerencias ordenadas.

```jsx
import { SmartSuggestionList } from './suggestions';

function UnassignedRoutesPanel() {
  const [selectedRoute, setSelectedRoute] = useState(null);
  const allBuses = useStore(state => state.buses);
  
  const handleApplySuggestion = (suggestion) => {
    // Aplicar la sugerencia al timeline
    console.log('Aplicando sugerencia:', suggestion);
  };
  
  return (
    <div className="unassigned-panel">
      {selectedRoute && (
        <SmartSuggestionList
          route={selectedRoute}
          allBuses={allBuses}
          onApply={handleApplySuggestion}
          autoSortEnabled={true}
        />
      )}
    </div>
  );
}
```

### 2. SmartSuggestionCard
Tarjeta individual de sugerencia con indicadores visuales.

```jsx
import { SmartSuggestionCard } from './suggestions';

function CustomSuggestionView({ suggestion }) {
  return (
    <SmartSuggestionCard
      suggestion={suggestion}
      rank={1}
      onApply={() => console.log('Aplicado')}
    />
  );
}
```

### 3. AutoSortToggle
Toggle para activar/desactivar la auto-ordenación.

```jsx
import { AutoSortToggle } from './suggestions';

function Toolbar() {
  const [autoSort, setAutoSort] = useState(true);
  
  return (
    <AutoSortToggle
      enabled={autoSort}
      onToggle={setAutoSort}
    />
  );
}
```

### 4. SuggestionsSkeleton
Esqueleto de carga para las sugerencias.

```jsx
import { SuggestionsSkeleton } from './suggestions';

function LoadingState() {
  return <SuggestionsSkeleton count={3} />;
}
```

## Estructura de Datos de Sugerencia

```typescript
interface Suggestion {
  bus_id: string;           // ID del bus
  position: number;         // Posición sugerida en el timeline
  score: number;            // Puntuación 0-100
  estimated_start_time: string;  // Hora de inicio estimada (HH:MM)
  travel_time_from_prev: number; // Tiempo de viaje desde ruta anterior (min)
  buffer_time: number;      // Buffer disponible (min)
  factors: {
    prev_buffer: number;    // Score del buffer anterior (0-1)
    next_buffer: number;    // Score del buffer siguiente (0-1)
    geographic_proximity: number;  // Score de proximidad geográfica (0-1)
    time_alignment: number; // Score de alineación temporal (0-1)
  };
}
```

## Características Visuales

### Ranking
- **#1 (Oro)**: Badge amarillo con borde destacado
- **#2 (Plata)**: Badge gris claro
- **#3 (Bronce)**: Badge ámbar/naranja
- **#4+**: Badge gris oscuro

### Score/Compatibilidad
- **≥90%**: Verde - Excelente compatibilidad
- **≥70%**: Amarillo - Buena compatibilidad
- **≥50%**: Naranja - Compatibilidad aceptable
- **<50%**: Rojo - Compatibilidad débil

### Indicadores de Factores
- ✓ Buen buffer anterior (prev_buffer > 0.7)
- ✓ Buen buffer siguiente (next_buffer > 0.7)
- 📍 Cerca geográficamente (geographic_proximity > 0.7)
- ⏰ Alineación temporal perfecta (time_alignment > 0.8)

### Mejor Opción (#1)
- Borde dorado con glow
- Badge "⭐ MEJOR"
- Botón destacado amarillo con texto "Aplicar Mejor Opción"
- Fondo degradado sutil

## Integración con el Panel de Rutas Libres

```jsx
// En UnassignedRoutesPanel.jsx o similar
import { SmartSuggestionList } from '../suggestions';

export function UnassignedRoutesPanel() {
  const unassignedRoutes = useStore(state => state.unassignedRoutes);
  const buses = useStore(state => state.buses);
  const [expandedRoute, setExpandedRoute] = useState(null);
  const applySuggestion = useStore(state => state.applySuggestion);
  
  return (
    <div className="unassigned-routes-panel">
      <h3>Rutas Libres</h3>
      
      {unassignedRoutes.map(route => (
        <div key={route.id} className="route-item">
          {/* Header de la ruta */}
          <div onClick={() => setExpandedRoute(route.id)}>
            {route.name}
          </div>
          
          {/* Panel de sugerencias expandible */}
          {expandedRoute === route.id && (
            <SmartSuggestionList
              route={route}
              allBuses={buses}
              onApply={(suggestion) => {
                applySuggestion(route.id, suggestion);
                setExpandedRoute(null);
              }}
            />
          )}
        </div>
      ))}
    </div>
  );
}
```

## Estados del Componente

### Loading
Muestra 3 skeletons animados mientras carga las sugerencias.

### Error
Muestra mensaje de error con botón para reintentar.

### Vacío
Muestra mensaje cuando no hay sugerencias disponibles.

### Con Datos
Muestra la lista de sugerencias ordenadas con todos los indicadores visuales.
