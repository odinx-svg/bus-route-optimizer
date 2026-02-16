/**
 * AutoSortToggle - Componente toggle para activar/desactivar auto-ordenación
 * 
 * Permite al usuario alternar entre:
 * - Auto-ordenación activada: sugerencias ordenadas por score (mejor primero)
 * - Auto-ordenación desactivada: sugerencias en orden original
 * 
 * @param {Object} props
 * @param {boolean} props.enabled - Estado actual del toggle
 * @param {Function} props.onToggle - Callback cuando cambia el estado
 */
export function AutoSortToggle({ enabled, onToggle }) {
  return (
    <div className="flex items-center justify-between p-3 bg-gray-750 rounded-lg border border-gray-700">
      <div className="flex items-center gap-2">
        <div className={`
          w-8 h-8 rounded-lg flex items-center justify-center transition-colors
          ${enabled ? 'bg-indigo-500/20 text-indigo-400' : 'bg-gray-700 text-gray-500'}
        `}>
          <svg 
            xmlns="http://www.w3.org/2000/svg" 
            className="w-4 h-4" 
            viewBox="0 0 24 24" 
            fill="none" 
            stroke="currentColor" 
            strokeWidth="2" 
            strokeLinecap="round" 
            strokeLinejoin="round"
          >
            {enabled ? (
              // Icono de orden descendente (mejor primero)
              <>
                <path d="m3 16 4 4 4-4" />
                <path d="M7 20V4" />
                <path d="M11 4h10" />
                <path d="M11 8h7" />
                <path d="M11 12h4" />
              </>
            ) : (
              // Icono de lista sin ordenar
              <>
                <line x1="8" y1="6" x2="21" y2="6" />
                <line x1="8" y1="12" x2="21" y2="12" />
                <line x1="8" y1="18" x2="21" y2="18" />
                <line x1="3" y1="6" x2="3.01" y2="6" />
                <line x1="3" y1="12" x2="3.01" y2="12" />
                <line x1="3" y1="18" x2="3.01" y2="18" />
              </>
            )}
          </svg>
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-medium text-gray-300">
            Auto-ordenar por compatibilidad
          </span>
          <span className="text-[10px] text-gray-500">
            {enabled ? 'Mostrando más compatible primero' : 'Orden original de sugerencias'}
          </span>
        </div>
      </div>
      
      {/* Toggle switch */}
      <button
        onClick={() => onToggle?.(!enabled)}
        className={`
          relative w-12 h-6 rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-gray-800
          ${enabled ? 'bg-indigo-600' : 'bg-gray-600'}
        `}
        role="switch"
        aria-checked={enabled}
        aria-label="Auto-ordenar por compatibilidad"
      >
        <span className="sr-only">
          {enabled ? 'Desactivar auto-ordenación' : 'Activar auto-ordenación'}
        </span>
        <span className={`
          absolute top-1 w-4 h-4 rounded-full bg-white shadow-md transition-transform duration-200 ease-in-out
          ${enabled ? 'translate-x-7' : 'translate-x-1'}
        `}>
          {/* Indicador visual del estado */}
          <span className={`
            absolute inset-0 flex items-center justify-center
            ${enabled ? 'text-indigo-600' : 'text-gray-400'}
          `}>
            <span className="w-1.5 h-1.5 rounded-full bg-current" />
          </span>
        </span>
      </button>
    </div>
  );
}

export default AutoSortToggle;
