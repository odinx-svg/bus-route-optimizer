import React from 'react';

/**
 * DropZoneIndicator - Indicador visual de zona de drop durante drag & drop
 * Muestra feedback visual según si se puede soltar o no
 */
export function DropZoneIndicator({ 
  isOver, 
  canDrop, 
  compatibility,
  size = 'normal' // 'small' | 'normal' | 'large'
}) {
  // Determinar el estado visual
  const getState = () => {
    if (!isOver) return 'idle';
    if (!canDrop) return 'blocked';
    if (compatibility && !compatibility.compatible) return 'incompatible';
    return 'compatible';
  };

  const state = getState();

  // Configuración de tamaños
  const sizes = {
    small: {
      container: 'min-w-[40px] h-12',
      icon: 'w-3 h-3',
      text: 'text-[8px]'
    },
    normal: {
      container: 'min-w-[60px] h-20',
      icon: 'w-5 h-5',
      text: 'text-xs'
    },
    large: {
      container: 'min-w-[80px] h-24',
      icon: 'w-6 h-6',
      text: 'text-sm'
    }
  };

  const dimension = sizes[size];

  // Configuración de estilos según estado
  const styles = {
    idle: {
      bg: 'bg-gray-800/50',
      border: 'border-gray-600',
      icon: 'text-gray-600',
      glow: ''
    },
    compatible: {
      bg: 'bg-green-500/20',
      border: 'border-green-500',
      icon: 'text-green-400',
      glow: 'shadow-[0_0_15px_rgba(34,197,94,0.3)]'
    },
    incompatible: {
      bg: 'bg-red-500/20',
      border: 'border-red-500',
      icon: 'text-red-400',
      glow: 'shadow-[0_0_15px_rgba(239,68,68,0.3)]'
    },
    blocked: {
      bg: 'bg-gray-700/50',
      border: 'border-gray-500',
      icon: 'text-gray-500',
      glow: ''
    }
  };

  const theme = styles[state];

  // Iconos según estado
  const icons = {
    idle: (
      <svg className={dimension.icon} fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
      </svg>
    ),
    compatible: (
      <svg className={dimension.icon} fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      </svg>
    ),
    incompatible: (
      <svg className={dimension.icon} fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      </svg>
    ),
    blocked: (
      <svg className={dimension.icon} fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
      </svg>
    )
  };

  // Mensajes según estado
  const messages = {
    idle: '',
    compatible: 'Soltar aquí',
    incompatible: 'No cabe',
    blocked: 'No permitido'
  };

  return (
    <div className={`
      ${dimension.container}
      rounded-lg border-2 border-dashed
      flex flex-col items-center justify-center
      transition-all duration-200 ease-out
      ${theme.bg}
      ${theme.border}
      ${state !== 'idle' ? 'scale-105 ' + theme.glow : ''}
      ${state === 'compatible' ? 'scale-110' : ''}
    `}>
      {/* Icono */}
      <div className={`
        ${theme.icon}
        transition-transform duration-200
        ${state === 'compatible' ? 'scale-110' : ''}
      `}>
        {icons[state]}
      </div>

      {/* Texto de estado */}
      {isOver && (
        <div className={`
          ${dimension.text}
          text-center mt-1 px-1
          ${theme.icon}
          animate-in fade-in duration-150
        `}>
          {messages[state]}
        </div>
      )}

      {/* Info de compatibilidad adicional */}
      {isOver && compatibility && canDrop && (
        <div className={`
          text-[9px] text-center mt-0.5 px-1.5 py-0.5 rounded
          ${compatibility.compatible 
            ? 'bg-green-900/50 text-green-300' 
            : 'bg-red-900/50 text-red-300'}
        `}>
          {compatibility.buffer_minutes > 0 ? '+' : ''}
          {compatibility.buffer_minutes?.toFixed(0)}m
        </div>
      )}
    </div>
  );
}

/**
 * DropZoneBetweenRoutes - Indicador de drop entre rutas existentes
 */
export function DropZoneBetweenRoutes({ 
  isOver, 
  canDrop, 
  compatibility,
  beforeRoute,
  afterRoute
}) {
  const state = isOver 
    ? (canDrop && compatibility?.compatible ? 'compatible' : 'incompatible')
    : 'idle';

  const styles = {
    idle: 'border-gray-700 bg-transparent',
    compatible: 'border-green-500 bg-green-500/20',
    incompatible: 'border-red-500 bg-red-500/20'
  };

  return (
    <div className={`
      w-4 h-16 mx-1 rounded
      border-2 border-dashed
      flex items-center justify-center
      transition-all duration-200
      ${styles[state]}
      ${isOver ? 'scale-110' : 'scale-100'}
    `}>
      {isOver && (
        <div className={`
          w-1.5 h-8 rounded-full
          ${state === 'compatible' ? 'bg-green-400' : 'bg-red-400'}
        `} />
      )}
    </div>
  );
}

/**
 * DropZoneTimeline - Zona de drop para toda la timeline de un bus
 */
export function DropZoneTimeline({ 
  isOver, 
  isEmpty,
  canDrop,
  compatibility,
  routeCount = 0
}) {
  const getState = () => {
    if (!isOver) return isEmpty ? 'empty' : 'idle';
    if (!canDrop) return 'blocked';
    if (compatibility && !compatibility.compatible) return 'incompatible';
    return 'compatible';
  };

  const state = getState();

  const styles = {
    empty: 'border-dashed border-gray-700 bg-gray-900/30',
    idle: 'border-transparent bg-gray-900/50',
    compatible: 'border-green-500/50 bg-green-500/10',
    incompatible: 'border-red-500/50 bg-red-500/10',
    blocked: 'border-gray-600/50 bg-gray-800/30'
  };

  return (
    <div className={`
      flex-1 flex items-center gap-1 min-h-[88px] rounded-lg p-3
      border-2 transition-all duration-200
      ${styles[state]}
    `}>
      {isEmpty && state === 'empty' && (
        <div className="flex items-center justify-center w-full text-gray-500 text-sm gap-2">
          <svg className="w-4 h-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <span>Arrastra rutas aquí</span>
        </div>
      )}

      {isOver && compatibility && (
        <div className={`
          absolute inset-0 flex items-center justify-center
          ${state === 'compatible' ? 'bg-green-500/5' : 'bg-red-500/5'}
        `}>
          <div className={`
            px-3 py-1.5 rounded-full text-sm font-medium
            ${state === 'compatible' 
              ? 'bg-green-900/80 text-green-300 border border-green-700' 
              : 'bg-red-900/80 text-red-300 border border-red-700'}
          `}>
            {state === 'compatible' ? '✓ Soltar aquí' : '✗ No cabe'}
          </div>
        </div>
      )}
    </div>
  );
}

export default DropZoneIndicator;
