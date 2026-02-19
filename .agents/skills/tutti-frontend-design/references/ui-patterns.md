# Patrones de UI Especificos

## Timeline Patterns

### Route Block States

```jsx
const routeBlockStyles = {
  // Estado base
  base: `
    absolute h-8 rounded-md
    border-l-4
    flex items-center px-2
    text-xs font-medium
    cursor-pointer
    select-none
    overflow-hidden
  `,
  
  // Tipos de ruta
  entry: 'bg-blue-500/20 border-blue-500 text-blue-300',
  exit: 'bg-emerald-500/20 border-emerald-500 text-emerald-300',
  
  // Estados interactivos
  default: 'hover:brightness-110',
  selected: 'ring-2 ring-white/50 brightness-110',
  dragging: 'opacity-70 scale-105 z-50 shadow-xl',
  locked: 'opacity-50 grayscale',
  
  // Estados de validacion
  valid: '',
  warning: 'bg-amber-500/20 border-amber-500',
  error: 'bg-red-500/20 border-red-500',
  conflict: 'animate-pulse bg-red-500/30 border-red-500',
};
```

### Time Markers

```jsx
// Marcas de hora en timeline
const HourMarkers = () => {
  const hours = Array.from({ length: 15 }, (_, i) => i + 6); // 6:00 - 20:00
  
  return (
    <div className="absolute inset-0 flex">
      {hours.map(hour => (
        <div 
          key={hour}
          className="flex-1 border-r border-[#253a4f]/30 relative"
        >
          <span className="
            absolute bottom-0 left-1
            text-[9px] text-gray-600
            font-mono
          ">
            {hour.toString().padStart(2, '0')}:00
          </span>
        </div>
      ))}
    </div>
  );
};
```

### Deadhead Visualization

```jsx
// Gap entre rutas (deadhead)
const DeadheadGap = ({ minutes, isValid }) => (
  <div 
    className={`
      absolute h-8 flex items-center justify-center
      ${isValid ? 'text-emerald-400' : 'text-red-400'}
    `}
    style={{ width: `${widthPercent}%` }}
  >
    <div className="
      flex items-center gap-1
      text-[9px] font-mono
    ">
      {!isValid && <AlertTriangle className="w-3 h-3" />}
      <span>{minutes}min</span>
    </div>
    
    {/* Linea conectadora */}
    <div className={`
      absolute inset-x-0 top-1/2 h-px
      ${isValid ? 'bg-emerald-500/30' : 'bg-red-500/50 dashed'}
      -translate-y-1/2
    `} />
  </div>
);
```

## Map Visualization

### Route Colors

```jsx
const routeColors = {
  entry: {
    line: '#3b82f6',
    fill: 'rgba(59, 130, 246, 0.1)',
    marker: '#60a5fa'
  },
  exit: {
    line: '#10b981', 
    fill: 'rgba(16, 185, 129, 0.1)',
    marker: '#34d399'
  },
  selected: {
    line: '#f59e0b',
    fill: 'rgba(245, 158, 11, 0.2)',
    marker: '#fbbf24'
  },
  conflict: {
    line: '#ef4444',
    fill: 'rgba(239, 68, 68, 0.2)',
    marker: '#f87171'
  }
};
```

### Stop Markers

```jsx
const StopMarker = ({ type, order, isSchool }) => (
  <div className={`
    w-6 h-6 rounded-full 
    flex items-center justify-center
    text-xs font-bold
    border-2
    ${isSchool ? 
      'bg-amber-500 border-amber-300 text-white' : 
      'bg-[#1a2d3f] border-gray-500 text-gray-300'
    }
  ">
    {order}
  </div>
);
```

## Data Display

### Stat Cards

```jsx
const StatCard = ({ label, value, trend, icon: Icon }) => (
  <div className="
    bg-[#1a2d3f] rounded-lg p-4
    border border-[#253a4f]
  ">
    <div className="flex items-start justify-between">
      <div>
        <p className="text-xs text-gray-500 uppercase tracking-wider">
          {label}
        </p>
        <p className="text-2xl font-bold text-gray-200 mt-1">
          {value}
        </p>
      </div>
      <div className="p-2 bg-[#253a4f] rounded-lg">
        <Icon className="w-5 h-5 text-gray-400" />
      </div>
    </div>
    
    {trend && (
      <div className={`
        flex items-center gap-1 mt-2 text-xs
        ${trend > 0 ? 'text-emerald-400' : 'text-red-400'}
      `}>
        {trend > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
        <span>{Math.abs(trend)}%</span>
        <span className="text-gray-500">vs anterior</span>
      </div>
    )}
  </div>
);
```

### Progress Indicators

```jsx
// Barra de progreso con pasos
const StepProgress = ({ steps, currentStep }) => (
  <div className="flex items-center gap-2">
    {steps.map((step, idx) => (
      <React.Fragment key={step.id}>
        <div className={`
          flex items-center gap-2 px-3 py-1.5 rounded-full text-xs
          ${idx < currentStep ? 'bg-emerald-500/20 text-emerald-400' :
            idx === currentStep ? 'bg-blue-500/20 text-blue-400 ring-1 ring-blue-500' :
            'bg-[#253a4f] text-gray-500'}
        `}>
          {idx < currentStep ? (
            <Check className="w-3 h-3" />
          ) : (
            <span className="w-4 h-4 rounded-full bg-current/20 flex items-center justify-center">
              {idx + 1}
            </span>
          )}
          <span>{step.label}</span>
        </div>
        
        {idx < steps.length - 1 && (
          <div className={`
            w-8 h-px
            ${idx < currentStep ? 'bg-emerald-500' : 'bg-[#253a4f]'}
          `} />
        )}
      </React.Fragment>
    ))}
  </div>
);
```

## Empty States

```jsx
const EmptyState = ({ 
  icon: Icon, 
  title, 
  description, 
  action 
}) => (
  <div className="
    flex flex-col items-center justify-center
    py-12 px-4 text-center
  ">
    <div className="
      w-16 h-16 rounded-full
      bg-[#253a4f] 
      flex items-center justify-center
      mb-4
    ">
      <Icon className="w-8 h-8 text-gray-500" />
    </div>
    
    <h3 className="text-lg font-medium text-gray-300">
      {title}
    </h3>
    
    <p className="text-sm text-gray-500 mt-1 max-w-sm">
      {description}
    </p>
    
    {action && (
      <div className="mt-6">
        {action}
      </div>
    )}
  </div>
);

// Uso
<EmptyState
  icon={MapPin}
  title="No hay rutas seleccionadas"
  description="Selecciona una ruta del panel para ver sus detalles"
/>
```

## Loading States

```jsx
// Tabla skeleton
const TableSkeleton = ({ rows = 5, cols = 4 }) => (
  <div className="space-y-2">
    {/* Header */}
    <div className="flex gap-4">
      {Array.from({ length: cols }).map((_, i) => (
        <Skeleton key={i} className="h-8 flex-1" />
      ))}
    </div>
    
    {/* Rows */}
    {Array.from({ length: rows }).map((_, rowIdx) => (
      <div key={rowIdx} className="flex gap-4">
        {Array.from({ length: cols }).map((_, colIdx) => (
          <Skeleton key={colIdx} className="h-10 flex-1" />
        ))}
      </div>
    ))}
  </div>
);

// Card skeleton
const CardSkeleton = () => (
  <div className="bg-[#1a2d3f] rounded-lg p-4 border border-[#253a4f]">
    <div className="flex items-start justify-between">
      <div className="space-y-2">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-8 w-16" />
      </div>
      <Skeleton className="h-10 w-10 rounded-lg" />
    </div>
    <Skeleton className="h-3 w-24 mt-4" />
  </div>
);
```

## Toast/Notifications

```jsx
const ToastStyles = {
  success: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
  error: 'bg-red-500/10 border-red-500/30 text-red-400',
  warning: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
  info: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
};

const Toast = ({ type, title, message, onClose }) => (
  <motion.div
    initial={{ opacity: 0, x: 50 }}
    animate={{ opacity: 1, x: 0 }}
    exit={{ opacity: 0, x: 50 }}
    className={`
      flex items-start gap-3 p-4 rounded-lg
      border backdrop-blur-sm
      ${ToastStyles[type]}
    `}
  >
    {type === 'success' && <CheckCircle className="w-5 h-5 shrink-0" />}
    {type === 'error' && <XCircle className="w-5 h-5 shrink-0" />}
    {type === 'warning' && <AlertTriangle className="w-5 h-5 shrink-0" />}
    {type === 'info' && <Info className="w-5 h-5 shrink-0" />}
    
    <div className="flex-1 min-w-0">
      <p className="font-medium">{title}</p>
      {message && <p className="text-sm opacity-80 mt-0.5">{message}</p>}
    </div>
    
    <button onClick={onClose} className="opacity-60 hover:opacity-100">
      <X className="w-4 h-4" />
    </button>
  </motion.div>
);
```

## Modal/Dialog

```jsx
const Modal = ({ isOpen, onClose, title, children, actions }) => (
  <AnimatePresence>
    {isOpen && (
      <>
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
        />
        
        {/* Modal */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          className="
            fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2
            w-full max-w-lg
            bg-[#1a2d3f] rounded-xl
            border border-[#253a4f]
            shadow-2xl
            z-50
          "
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-[#253a4f]">
            <h2 className="text-lg font-semibold text-gray-200">{title}</h2>
            <button onClick={onClose} className="text-gray-500 hover:text-gray-300">
              <X className="w-5 h-5" />
            </button>
          </div>
          
          {/* Content */}
          <div className="px-6 py-4">
            {children}
          </div>
          
          {/* Actions */}
          {actions && (
            <div className="flex justify-end gap-2 px-6 py-4 border-t border-[#253a4f] bg-[#0b141f]/50 rounded-b-xl">
              {actions}
            </div>
          )}
        </motion.div>
      </>
    )}
  </AnimatePresence>
);
```
