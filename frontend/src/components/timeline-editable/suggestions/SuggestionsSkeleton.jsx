/**
 * SuggestionsSkeleton - Componente de carga para las sugerencias
 * 
 * Muestra un esqueleto animado mientras se cargan las sugerencias.
 * Incluye múltiples tarjetas skeleton con animación pulsante.
 * 
 * @param {Object} props
 * @param {number} props.count - Número de skeletons a mostrar (default: 3)
 */
export function SuggestionsSkeleton({ count = 3 }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, index) => (
        <div 
          key={index}
          className="relative p-3 rounded-lg border border-gray-700 bg-gray-800/50 animate-pulse"
        >
          {/* Skeleton del badge de ranking */}
          <div className="absolute -top-2 -left-2 w-7 h-7 rounded-full bg-gray-700" />
          
          {/* Header skeleton */}
          <div className="flex items-center justify-between ml-5 mb-3">
            <div className="flex items-center gap-2">
              {/* Icono skeleton */}
              <div className="w-5 h-5 rounded-full bg-gray-700" />
              {/* Bus info skeleton */}
              <div className="flex flex-col gap-1">
                <div className="w-16 h-4 bg-gray-700 rounded" />
                <div className="w-12 h-3 bg-gray-700 rounded" />
              </div>
            </div>
            {/* Score skeleton */}
            <div className="flex flex-col items-end gap-1">
              <div className="w-12 h-6 bg-gray-700 rounded" />
              <div className="w-16 h-3 bg-gray-700 rounded" />
            </div>
          </div>

          {/* Progress bar skeleton */}
          <div className="ml-5 mb-3">
            <div className="w-full h-1.5 bg-gray-700 rounded-full" />
          </div>

          {/* Details skeleton */}
          <div className="ml-5 space-y-2">
            <div className="flex items-center justify-between">
              <div className="w-24 h-3 bg-gray-700 rounded" />
              <div className="w-12 h-3 bg-gray-700 rounded" />
            </div>
            <div className="flex items-center justify-between">
              <div className="w-28 h-3 bg-gray-700 rounded" />
              <div className="w-10 h-3 bg-gray-700 rounded" />
            </div>
            <div className="flex items-center justify-between">
              <div className="w-20 h-3 bg-gray-700 rounded" />
              <div className="w-8 h-3 bg-gray-700 rounded" />
            </div>
          </div>

          {/* Factors skeleton */}
          <div className="ml-5 mt-3 flex flex-wrap gap-1.5">
            <div className="w-20 h-5 bg-gray-700 rounded" />
            <div className="w-24 h-5 bg-gray-700 rounded" />
          </div>

          {/* Button skeleton */}
          <div className="w-full mt-3 h-9 bg-gray-700 rounded-lg" />
        </div>
      ))}
    </div>
  );
}

export default SuggestionsSkeleton;
