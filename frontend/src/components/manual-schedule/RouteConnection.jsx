import React from 'react';

/**
 * RouteConnection - Componente visual para mostrar la conexión entre dos rutas
 * Incluye flecha direccional, badge con buffer y warning si es necesario
 */
export function RouteConnection({ routeA, routeB, validation, showDetails = false }) {
  // Valores por defecto si no hay validación
  const { 
    compatible = false, 
    buffer_minutes = 0, 
    travel_time = 0 
  } = validation || {};

  // Determinar el estado de la conexión
  const getConnectionStatus = () => {
    if (!validation) return 'neutral';
    if (!compatible) return 'incompatible';
    if (buffer_minutes < 5) return 'warning';
    return 'compatible';
  };

  const status = getConnectionStatus();

  // Configuración de colores según estado
  const styles = {
    compatible: {
      line: 'bg-green-500',
      arrow: 'border-l-green-500',
      badge: 'bg-green-900 text-green-300 border-green-700',
      icon: 'text-green-500'
    },
    incompatible: {
      line: 'bg-red-500',
      arrow: 'border-l-red-500',
      badge: 'bg-red-900 text-red-300 border-red-700',
      icon: 'text-red-500'
    },
    warning: {
      line: 'bg-amber-500',
      arrow: 'border-l-amber-500',
      badge: 'bg-amber-900 text-amber-300 border-amber-700',
      icon: 'text-amber-500'
    },
    neutral: {
      line: 'bg-gray-600',
      arrow: 'border-l-gray-600',
      badge: 'bg-gray-800 text-gray-400 border-gray-600',
      icon: 'text-gray-600'
    }
  };

  const theme = styles[status];

  return (
    <div className="flex flex-col items-center gap-1">
      {/* Línea de conexión con flecha */}
      <div className="flex items-center">
        {/* Línea horizontal */}
        <div className={`
          w-8 h-0.5 ${theme.line}
          relative transition-colors duration-200
        `}>
          {/* Punta de flecha */}
          <div className={`
            absolute right-0 top-1/2 -translate-y-1/2
            w-0 h-0 border-t-[3px] border-b-[3px] border-l-[6px]
            border-t-transparent border-b-transparent
            ${theme.arrow}
            transition-colors duration-200
          `} />
        </div>

        {/* Badge con buffer */}
        <div className={`
          text-[10px] px-2 py-0.5 rounded ml-1.5
          border font-mono tabular-nums
          ${theme.badge}
          transition-colors duration-200
        `}>
          {buffer_minutes > 0 ? '+' : ''}{buffer_minutes.toFixed(0)}m
        </div>

        {/* Icono de warning si es justo o incompatible */}
        {status === 'warning' && (
          <span 
            className="text-amber-500 ml-1" 
            title="Buffer justo - menos de 5 minutos"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </span>
        )}
        
        {status === 'incompatible' && (
          <span 
            className="text-red-500 ml-1" 
            title="Conexión incompatible"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </span>
        )}
      </div>

      {/* Detalles adicionales (opcional) */}
      {showDetails && validation && (
        <div className="text-[9px] text-gray-500 text-center">
          <div>viaje: {travel_time.toFixed(0)}m</div>
        </div>
      )}
    </div>
  );
}

/**
 * RouteConnectionCompact - Versión minimalista para espacios reducidos
 */
export function RouteConnectionCompact({ validation }) {
  const { compatible = false, buffer_minutes = 0 } = validation || {};
  
  if (!validation) return null;

  const status = compatible 
    ? (buffer_minutes < 5 ? 'warning' : 'compatible')
    : 'incompatible';

  const colors = {
    compatible: 'text-green-500',
    incompatible: 'text-red-500',
    warning: 'text-amber-500'
  };

  return (
    <div className={`flex items-center ${colors[status]}`}>
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
      </svg>
      <span className={`
        text-[9px] ml-0.5 px-1 rounded
        ${status === 'compatible' ? 'bg-green-900/50' : ''}
        ${status === 'incompatible' ? 'bg-red-900/50' : ''}
        ${status === 'warning' ? 'bg-amber-900/50' : ''}
      `}>
        {buffer_minutes > 0 ? '+' : ''}{buffer_minutes.toFixed(0)}m
      </span>
    </div>
  );
}

/**
 * RouteConnectionList - Lista de conexiones entre múltiples rutas
 */
export function RouteConnectionList({ routes, validations = [] }) {
  if (routes.length < 2) return null;

  return (
    <div className="flex items-center gap-1">
      {routes.map((route, index) => {
        const nextRoute = routes[index + 1];
        if (!nextRoute) return null;

        const validation = validations[index];

        return (
          <div key={`conn-${route.id}-${nextRoute.id}`} className="flex items-center">
            <div className="w-2 h-2 rounded-full bg-gray-600" />
            <RouteConnection 
              routeA={route} 
              routeB={nextRoute} 
              validation={validation}
            />
          </div>
        );
      })}
    </div>
  );
}

export default RouteConnection;
