---
name: tutti-frontend-design
description: Diseno UI/UX y estilos visuales para Tutti Fleet Optimizer. Usar cuando se necesite crear o modificar interfaces de usuario, componentes visuales, animaciones, responsive design, sistema de diseño, temas, o mejorar la experiencia de usuario. Incluye Tailwind CSS, Framer Motion, colores, tipografia y patrones de UI especificos del proyecto.
---

# Tutti Frontend Design Skill

## Sistema de Diseno

### Paleta de Colores

```css
/* Primary - Azul profesional */
--color-bg-primary: #0b141f;        /* Fondo principal */
--color-bg-panel: #1a2d3f;          /* Paneles/cards */
--color-bg-hover: #253a4f;          /* Hover states */
--color-border: #253a4f;            /* Bordes */

/* Accent - Azul cian */
--color-accent: #64b5f6;            /* Acento principal */
--color-accent-hover: #90caf9;      /* Acento hover */
--color-accent-muted: #42a5f5;      /* Acento muted */

/* Estados */
--color-success: #10b981;           /* Exito/valido */
--color-warning: #f59e0b;           /* Advertencia */
--color-error: #ef4444;             /* Error/conflicto */
--color-info: #3b82f6;              /* Informacion */

/* Texto */
--color-text-primary: #e2e8f0;      /* Texto principal */
--color-text-secondary: #94a3b8;    /* Texto secundario */
--color-text-muted: #64748b;        /* Texto muted */
--color-text-inverse: #0b141f;      /* Texto en fondos claros */
```

### Tipografia

```css
/* Fuente principal */
font-family: 'Inter', system-ui, -apple-system, sans-serif;

/* Jerarquia */
--text-xs: 10px;    /* Labels, badges */
--text-sm: 12px;    /* Secundario, captions */
--text-base: 13px;  /* Body normal */
--text-md: 14px;    /* Emphasis */
--text-lg: 16px;    /* Titulos pequenos */
--text-xl: 18px;    /* Titulos */
--text-2xl: 20px;   /* Titulos grandes */

/* Peso */
--font-normal: 400;
--font-medium: 500;
--font-semibold: 600;
--font-bold: 700;

/* Tracking especial para UI tecnica */
.tracking-tech {
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
```

### Espaciado

```css
/* Escala de espaciado */
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 20px;
--space-6: 24px;
--space-8: 32px;

/* Layout */
--layout-gap: 12px;           /* Gap entre elementos */
--layout-padding: 16px;       /* Padding de contenedores */
--panel-radius: 8px;          /* Border radius de paneles */
--card-radius: 6px;           /* Border radius de cards */
--button-radius: 6px;         /* Border radius de botones */
```

## Componentes UI

### Botones

```jsx
// Variantes de botones
const buttonVariants = {
  primary: `
    bg-blue-600 hover:bg-blue-500 
    text-white font-medium
    px-4 py-2 rounded-md
    transition-colors duration-200
    disabled:opacity-50 disabled:cursor-not-allowed
  `,
  
  secondary: `
    bg-[#1a2d3f] hover:bg-[#253a4f]
    text-gray-200 font-medium
    px-4 py-2 rounded-md
    border border-[#253a4f]
    transition-colors duration-200
  `,
  
  ghost: `
    bg-transparent hover:bg-[#253a4f]/50
    text-gray-300
    px-3 py-1.5 rounded-md
    transition-colors duration-200
  `,
  
  danger: `
    bg-red-600 hover:bg-red-500
    text-white font-medium
    px-4 py-2 rounded-md
    transition-colors duration-200
  `,
  
  icon: `
    p-2 rounded-md
    hover:bg-[#253a4f]
    text-gray-400 hover:text-gray-200
    transition-colors duration-200
  `
};
```

### Cards/Paneles

```jsx
// Panel base
const Panel = ({ children, className = '' }) => (
  <div className={`
    bg-[#1a2d3f] 
    border border-[#253a4f] 
    rounded-lg 
    ${className}
  `}>
    {children}
  </div>
);

// Card con hover
const HoverCard = ({ children }) => (
  <div className="
    bg-[#1a2d3f] 
    border border-[#253a4f] 
    rounded-lg 
    p-4
    hover:border-blue-500/50
    hover:shadow-lg hover:shadow-blue-500/10
    transition-all duration-300
  ">
    {children}
  </div>
);
```

### Formularios

```jsx
// Input
const Input = ({ error, ...props }) => (
  <input
    className={`
      w-full
      bg-[#0b141f]
      border ${error ? 'border-red-500' : 'border-[#253a4f]'}
      rounded-md
      px-3 py-2
      text-gray-200 text-sm
      placeholder:text-gray-600
      focus:outline-none focus:border-blue-500
      focus:ring-1 focus:ring-blue-500
      transition-colors
    `}
    {...props}
  />
);

// Select
const Select = ({ options, ...props }) => (
  <div className="relative">
    <select
      className="
        w-full
        bg-[#0b141f]
        border border-[#253a4f]
        rounded-md
        px-3 py-2 pr-8
        text-gray-200 text-sm
        focus:outline-none focus:border-blue-500
        appearance-none
      "
      {...props}
    >
      {options.map(opt => (
        <option key={opt.value} value={opt.value}>{opt.label}</option>
      ))}
    </select>
    <ChevronDown className="
      absolute right-2 top-1/2 -translate-y-1/2
      w-4 h-4 text-gray-500
      pointer-events-none
    " />
  </div>
);
```

### Badges y Status

```jsx
// Badge de estado
const StatusBadge = ({ status }) => {
  const styles = {
    active: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    pending: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    error: 'bg-red-500/20 text-red-400 border-red-500/30',
    inactive: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  };
  
  return (
    <span className={`
      inline-flex items-center gap-1.5
      px-2 py-0.5 rounded-full
      text-xs font-medium
      border
      ${styles[status]}
    `}>
      <span className={`
        w-1.5 h-1.5 rounded-full
        ${status === 'active' ? 'bg-emerald-400 animate-pulse' : ''}
      `} />
      {status}
    </span>
  );
};

// Tag pequeno
const Tag = ({ children, color = 'blue' }) => (
  <span className={`
    inline-flex items-center
    px-2 py-0.5 rounded
    text-[10px] font-semibold uppercase tracking-wider
    ${color === 'blue' && 'bg-blue-500/20 text-blue-400'}
    ${color === 'green' && 'bg-emerald-500/20 text-emerald-400'}
    ${color === 'amber' && 'bg-amber-500/20 text-amber-400'}
    ${color === 'red' && 'bg-red-500/20 text-red-400'}
  `}>
    {children}
  </span>
);
```

## Animaciones

### Transiciones Base

```css
/* Transicion suave */
.transition-smooth {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Transicion rapida */
.transition-fast {
  transition: all 0.15s ease-out;
}

/* Transicion lenta */
.transition-slow {
  transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}
```

### Animaciones de Entrada (Framer Motion)

```jsx
// Fade in + slide up
const fadeInUp = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -10 },
  transition: { duration: 0.2, ease: 'easeOut' }
};

// Scale in
const scaleIn = {
  initial: { opacity: 0, scale: 0.95 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.95 },
  transition: { duration: 0.15 }
};

// Stagger children
const staggerContainer = {
  animate: {
    transition: {
      staggerChildren: 0.05
    }
  }
};

// Usage
<motion.div
  initial="initial"
  animate="animate"
  exit="exit"
  variants={fadeInUp}
>
  Content
</motion.div>
```

### Micro-interacciones

```jsx
// Hover scale
const HoverScale = ({ children }) => (
  <motion.div
    whileHover={{ scale: 1.02 }}
    whileTap={{ scale: 0.98 }}
    transition={{ duration: 0.15 }}
  >
    {children}
  </motion.div>
);

// Pulse para indicadores activos
const ActiveIndicator = () => (
  <span className="relative flex h-2 w-2">
    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
  </span>
);

// Skeleton loading
const Skeleton = ({ className }) => (
  <div className={`
    animate-pulse
    bg-[#253a4f]/50
    rounded
    ${className}
  `} />
);
```

## Layout Patterns

### Grid de Dashboard

```jsx
// Layout principal del studio
const StudioLayout = () => (
  <div className="
    h-screen
    flex flex-col
    bg-[#0b141f]
  ">
    {/* Header */}
    <header className="h-14 border-b border-[#253a4f] px-4 flex items-center">
      {/* ... */}
    </header>
    
    {/* Main content */}
    <div className="flex-1 flex overflow-hidden">
      {/* Sidebar */}
      <aside className="w-72 border-r border-[#253a4f] overflow-y-auto">
        {/* ... */}
      </aside>
      
      {/* Workspace */}
      <main className="flex-1 overflow-auto p-4">
        {/* ... */}
      </main>
      
      {/* Details panel */}
      <aside className="w-80 border-l border-[#253a4f] overflow-y-auto">
        {/* ... */}
      </aside>
    </div>
  </div>
);
```

### Timeline Layout

```jsx
// Fila de bus en timeline
const BusTimelineRow = () => (
  <div className="flex items-center gap-3 py-2">
    {/* Label del bus */}
    <div className="w-24 shrink-0">
      <BusLabel />
    </div>
    
    {/* Track del timeline */}
    <div className="flex-1 relative h-12 bg-[#0b141f] rounded-md">
      {/* Marcas de hora */}
      <HourMarkers />
      
      {/* Bloques de ruta */}
      <div className="absolute inset-0">
        {routeBlocks.map(block => (
          <RouteBlock 
            key={block.id}
            style={{
              left: `${block.startPercent}%`,
              width: `${block.durationPercent}%`
            }}
          />
        ))}
      </div>
    </div>
  </div>
);
```

### Split Panel Resizable

```jsx
// Panel dividido con resize handle
const ResizableSplit = ({ left, right }) => {
  const [split, setSplit] = useState(60);
  
  return (
    <div className="flex h-full">
      <div style={{ width: `${split}%` }} className="overflow-auto">
        {left}
      </div>
      
      {/* Resize handle */}
      <div 
        className="w-1 bg-[#253a4f] cursor-col-resize hover:bg-blue-500 transition-colors"
        onMouseDown={handleResizeStart}
      />
      
      <div style={{ width: `${100 - split}%` }} className="overflow-auto">
        {right}
      </div>
    </div>
  );
};
```

## Responsive Design

### Breakpoints

```css
/* Mobile first */
sm: 640px   /* Tablets pequenas */
md: 768px   /* Tablets */
lg: 1024px  /* Desktop */
xl: 1280px  /* Desktop grande */
```

### Patterns Responsivos

```jsx
// Sidebar colapsable
const ResponsiveSidebar = ({ isOpen, onClose }) => (
  <>
    {/* Mobile: Overlay + drawer */}
    <div className={`
      fixed inset-0 z-50 lg:hidden
      ${isOpen ? 'block' : 'hidden'}
    `}>
      <div 
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
      />
      <div className="absolute left-0 top-0 bottom-0 w-72 bg-[#1a2d3f]">
        {/* Sidebar content */}
      </div>
    </div>
    
    {/* Desktop: Sidebar estatico */}
    <div className="hidden lg:block w-72 h-full">
      {/* Sidebar content */}
    </div>
  </>
);

// Grid adaptativo
const ResponsiveGrid = ({ items }) => (
  <div className="
    grid 
    grid-cols-1 
    sm:grid-cols-2 
    lg:grid-cols-3 
    xl:grid-cols-4 
    gap-4
  ">
    {items.map(item => <Card key={item.id} {...item} />)}
  </div>
);
```

## Accesibilidad (a11y)

### Patrones A11y

```jsx
// Boton con aria
<button
  aria-label="Optimizar rutas"
  aria-pressed={isOptimizing}
  disabled={isOptimizing}
  className="..."
>
  {isOptimizing ? <LoadingIcon /> : <PlayIcon />}
</button>

// Focus visible
*:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}

// Skip link
<a href="#main-content" className="sr-only focus:not-sr-only">
  Saltar al contenido principal
</a>

// Alertas live regions
<div role="alert" aria-live="polite" className="sr-only">
  {notificationMessage}
</div>
```

### Contraste de Color

```css
/* Todas las combinaciones deben cumplir WCAG AA */
/* Texto principal sobre fondo: #e2e8f0 / #0b141f = 12.6:1 ✓ */
/* Texto secundario sobre fondo: #94a3b8 / #0b141f = 7.2:1 ✓ */
/* Boton primario: white / #2563eb = 4.5:1 ✓ */
```

## Referencias

- `references/ui-patterns.md`: Patrones de UI especificos
- `references/animations.md`: Guia de animaciones avanzadas
- `assets/tokens.json`: Design tokens
