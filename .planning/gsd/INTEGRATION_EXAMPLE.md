# Ejemplo de Integración - UI Components

## Uso Rápido (Copy-Paste)

### 1. ProgressBar

```jsx
import { ProgressBar } from '../components/ui';

// Reemplazar barras de progreso simples
<div className="w-full bg-slate-700 rounded-full h-2">
  <div className="bg-blue-500 h-2 rounded-full" style={{ width: '75%' }} />
</div>

// Por:
<ProgressBar progress={75} size="md" showPercentage />
```

**Resultado:** Barra con gradiente azul-violeta + "75%" al lado

---

### 2. EmptyState

```jsx
import { EmptyState } from '../components/ui';
import { MapPin } from 'lucide-react';

// En lugar de:
{routes.length === 0 && (
  <p className="text-gray-500">No hay rutas</p>
)}

// Usar:
{routes.length === 0 && (
  <EmptyState
    icon={MapPin}
    title="Sin rutas disponibles"
    description="Carga un archivo Excel para comenzar a trabajar con rutas."
  />
)}
```

**Resultado:** Card estilizado con icono, título y descripción centrados

---

### 3. AvatarStack

```jsx
import { AvatarStack } from '../components/ui';

// Mostrar conductores asignados a un bus
const drivers = [
  { id: 1, name: 'Juan Perez', color: '#3b82f6' },
  { id: 2, name: 'Maria Garcia', color: '#10b981' },
  { id: 3, name: 'Carlos Lopez', color: '#f59e0b' },
];

<AvatarStack items={drivers} max={3} size="sm" />
```

**Resultado:** 3 círculos coloreados con overlap + "+1" si hay más

---

### 4. CSS Enhancements (Opt-in)

```jsx
// En cualquier componente existente, agregar clases:

// Header con gradiente sutil
<header className="control-header gradient-header">
  {/* contenido existente */}
</header>

// Card con glow al seleccionar
<div className={`control-panel ${isSelected ? 'glow-blue' : ''}`}>
  {/* contenido */}
</div>

// Badge moderno
<span className="badge-modern badge-blue">Entry</span>
```

---

## Importar CSS

En `frontend/src/index.css`, agregar al final:

```css
/* Mejoras visuales opcionales */
@import './styles/enhancements-safe.css';
```

---

## Preview Visual

### Antes vs Después

| Elemento | Antes (Tutti) | Después (G.Take style) |
|----------|---------------|------------------------|
| Progress | Barra azul sólida | Gradiente azul→violeta + % |
| Empty | Texto simple | Card con icono estilizado |
| Avatars | No existía | Stack con overlap |
| Header | Sólido #0b141f | Con gradiente sutil |

---

## Próximos Pasos Sugeridos

1. **Probar en desarrollo:**
   ```bash
   cd frontend
   npm run dev
   ```

2. **Integrar en componentes existentes** (uno por uno):
   - Sidebar: Agregar `gradient-header`
   - Route cards: Agregar `hover-lift`
   - Badges: Cambiar a `badge-modern`

3. **Commit cada cambio:**
   ```bash
   git add <archivo>
   git commit -m "ui: add hover-lift to RouteBlock"
   ```
