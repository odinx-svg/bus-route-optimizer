import React from 'react';

/**
 * CompatibilityTooltip - Popup informativo sobre compatibilidad entre rutas
 * Muestra información detallada al intentar soltar una ruta
 */
export function CompatibilityTooltip({ 
  routeA, 
  routeB, 
  isCompatible, 
  bufferMinutes,
  position = 'top',
  conflicts = [],
}) {
  // Formatear el buffer de tiempo
  const formatBuffer = (minutes) => {
    if (minutes >= 60) {
      const hours = Math.floor(minutes / 60);
      const mins = minutes % 60;
      return mins > 0 ? `${hours}h ${mins}min` : `${hours}h`;
    }
    return `${minutes}min`;
  };

  // Posicionamiento del tooltip
  const positions = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  };

  // Flecha del tooltip
  const arrows = {
    top: 'top-full left-1/2 -translate-x-1/2 border-t-green-900',
    bottom: 'bottom-full left-1/2 -translate-x-1/2 border-b-green-900',
    left: 'left-full top-1/2 -translate-y-1/2 border-l-green-900',
    right: 'right-full top-1/2 -translate-y-1/2 border-r-green-900',
  };

  const arrowError = {
    top: 'top-full left-1/2 -translate-x-1/2 border-t-red-900',
    bottom: 'bottom-full left-1/2 -translate-x-1/2 border-b-red-900',
    left: 'left-full top-1/2 -translate-y-1/2 border-l-red-900',
    right: 'right-full top-1/2 -translate-y-1/2 border-r-red-900',
  };

  if (isCompatible) {
    return (
      <div className={`absolute ${positions[position]} z-50`}>
        <div className="
          bg-green-900/95 backdrop-blur-sm text-green-100 
          px-3 py-2.5 rounded-lg text-xs 
          border border-green-700/50 shadow-xl shadow-green-900/30
          min-w-[140px]
        ">
          {/* Header con check */}
          <div className="flex items-center gap-2 mb-1.5">
            <div className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center">
              <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <span className="font-semibold text-green-50">Compatible</span>
          </div>

          {/* Buffer info */}
          <div className="space-y-1 text-green-200/80">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase tracking-wider">Buffer:</span>
              <span className="font-mono font-medium text-green-100">{formatBuffer(bufferMinutes)}</span>
            </div>
            
            {/* Timeline visual */}
            <div className="mt-2 pt-2 border-t border-green-700/50">
              <div className="flex items-center gap-1 text-[10px]">
                <span className="text-green-300">{routeA?.endTime}</span>
                <div className="flex-1 h-1 bg-green-700 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-green-400 rounded-full"
                    style={{ width: `${Math.min((bufferMinutes / 60) * 100, 100)}%` }}
                  />
                </div>
                <span className="text-green-300">{routeB?.startTime}</span>
              </div>
            </div>
          </div>
        </div>
        
        {/* Flecha */}
        <div className={`
          absolute w-0 h-0 
          border-4 border-transparent
          ${arrows[position]}
        `} />
      </div>
    );
  }

  // Estado incompatible
  return (
    <div className={`absolute ${positions[position]} z-50`}>
      <div className="
        bg-red-900/95 backdrop-blur-sm text-red-100 
        px-3 py-2.5 rounded-lg text-xs 
        border border-red-700/50 shadow-xl shadow-red-900/30
        min-w-[160px]
      ">
        {/* Header con X */}
        <div className="flex items-center gap-2 mb-1.5">
          <div className="w-5 h-5 rounded-full bg-red-500 flex items-center justify-center">
            <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <span className="font-semibold text-red-50">Incompatible</span>
        </div>

        {/* Info del conflicto */}
        <div className="space-y-1.5 text-red-200/80">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-wider">Faltan:</span>
            <span className="font-mono font-medium text-red-100">
              {formatBuffer(Math.abs(bufferMinutes))}
            </span>
          </div>

          {/* Timeline visual del conflicto */}
          <div className="mt-2 pt-2 border-t border-red-700/50">
            <div className="flex items-center gap-1 text-[10px]">
              <span className="text-red-300">{routeA?.endTime}</span>
              <div className="flex-1 flex items-center justify-center">
                <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              </div>
              <span className="text-red-300">{routeB?.startTime}</span>
            </div>
            <div className="text-center text-[9px] text-red-400 mt-0.5">
              Solapamiento detectado
            </div>
          </div>

          {/* Lista de conflictos si existen */}
          {conflicts.length > 0 && (
            <div className="mt-2 pt-2 border-t border-red-700/30">
              <div className="text-[10px] text-red-300 mb-1">Conflictos:</div>
              <ul className="space-y-0.5">
                {conflicts.map((conflict, idx) => (
                  <li key={idx} className="text-[9px] text-red-400 flex items-start gap-1">
                    <span className="text-red-500">•</span>
                    {conflict}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
      
      {/* Flecha */}
      <div className={`
        absolute w-0 h-0 
        border-4 border-transparent
        ${arrowError[position]}
      `} />
    </div>
  );
}

/**
 * CompactCompatibilityIndicator - Indicador compacto de compatibilidad
 * Para usar en lugares con poco espacio
 */
export function CompactCompatibilityIndicator({ isCompatible, bufferMinutes }) {
  if (isCompatible) {
    return (
      <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-green-500/10 border border-green-500/30">
        <div className="w-2 h-2 rounded-full bg-green-500" />
        <span className="text-[10px] text-green-400 font-medium">
          +{bufferMinutes}min
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-red-500/10 border border-red-500/30">
      <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
      <span className="text-[10px] text-red-400 font-medium">
        -{Math.abs(bufferMinutes)}min
      </span>
    </div>
  );
}

/**
 * CompatibilityBadge - Badge simple de compatibilidad
 */
export function CompatibilityBadge({ status, bufferMinutes }) {
  const configs = {
    compatible: {
      bg: 'bg-green-500/20',
      border: 'border-green-500/40',
      text: 'text-green-400',
      icon: (
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      ),
    },
    incompatible: {
      bg: 'bg-red-500/20',
      border: 'border-red-500/40',
      text: 'text-red-400',
      icon: (
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      ),
    },
    warning: {
      bg: 'bg-amber-500/20',
      border: 'border-amber-500/40',
      text: 'text-amber-400',
      icon: (
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      ),
    },
  };

  const config = configs[status] || configs.warning;

  return (
    <div className={`
      inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full
      ${config.bg} ${config.border} border
      ${config.text} text-[10px] font-medium
    `}>
      {config.icon}
      <span>
        {status === 'compatible' && bufferMinutes !== undefined && `+${bufferMinutes}min`}
        {status === 'incompatible' && bufferMinutes !== undefined && `-${Math.abs(bufferMinutes)}min`}
        {status === 'warning' && 'Cuidado'}
      </span>
    </div>
  );
}

/**
 * CompatibilityPreviewOverlay - Overlay de preview durante drag
 */
export function CompatibilityPreviewOverlay({ 
  isVisible, 
  position, 
  compatibility,
  message,
}) {
  if (!isVisible) return null;

  const colors = {
    compatible: 'bg-green-500/20 border-green-500/50 text-green-300',
    incompatible: 'bg-red-500/20 border-red-500/50 text-red-300',
    neutral: 'bg-gray-500/20 border-gray-500/50 text-gray-300',
  };

  return (
    <div 
      className={`
        fixed pointer-events-none z-50
        px-3 py-2 rounded-lg border backdrop-blur-sm
        ${colors[compatibility] || colors.neutral}
      `}
      style={{
        left: position?.x || 0,
        top: position?.y || 0,
        transform: 'translate(-50%, -100%) translateY(-8px)',
      }}
    >
      <span className="text-xs font-medium whitespace-nowrap">{message}</span>
      
      {/* Flecha hacia abajo */}
      <div className="
        absolute top-full left-1/2 -translate-x-1/2
        w-0 h-0 border-l-4 border-r-4 border-t-4
        border-l-transparent border-r-transparent
        border-t-current opacity-50
      " />
    </div>
  );
}

export default CompatibilityTooltip;
