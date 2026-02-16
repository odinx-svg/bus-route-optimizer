/**
 * SmartSuggestionCard - Tarjeta de sugerencia inteligente con indicadores visuales
 * 
 * Muestra una sugerencia con:
 * - Badge de ranking con colores (oro, plata, bronce)
 * - Indicadores de color según puntuación
 * - Iconos de compatibilidad
 * - Todos los factores (buffer, geografía, etc.)
 * - Botón destacado para la mejor opción
 * 
 * @param {Object} props
 * @param {Object} props.suggestion - Datos de la sugerencia
 * @param {number} props.rank - Posición en el ranking (1, 2, 3...)
 * @param {Function} props.onApply - Callback al hacer click en aplicar
 */
export function SmartSuggestionCard({ suggestion, rank, onApply }) {
  // Normalizar los datos de la sugerencia
  const busId = suggestion.bus_id || suggestion.busId;
  const position = suggestion.position ?? 0;
  const score = Math.round(suggestion.score || 0);
  const estimatedStartTime = suggestion.estimated_start_time || suggestion.startTime || '--:--';
  const travelTimeFromPrev = suggestion.travel_time_from_prev ?? 0;
  const bufferTime = suggestion.buffer_time ?? suggestion.buffer_minutes ?? 0;
  
  // Normalizar factores
  const factors = suggestion.factors || {
    prev_buffer: suggestion.prev_buffer_score ?? 0,
    next_buffer: suggestion.next_buffer_score ?? 0,
    geographic_proximity: suggestion.geographic_score ?? 0.5,
    time_alignment: suggestion.time_alignment_score ?? 0.5
  };

  // Determinar color del ranking (oro, plata, bronce)
  const getRankColor = (rank) => {
    if (rank === 1) return 'bg-yellow-500 text-black border-yellow-400'; // Oro
    if (rank === 2) return 'bg-gray-300 text-black border-gray-200';     // Plata
    if (rank === 3) return 'bg-amber-600 text-white border-amber-500';   // Bronce
    return 'bg-gray-700 text-gray-300 border-gray-600';
  };

  // Determinar color del score
  const getScoreColor = (scoreValue) => {
    if (scoreValue >= 90) return 'text-green-400';
    if (scoreValue >= 70) return 'text-yellow-400';
    if (scoreValue >= 50) return 'text-orange-400';
    return 'text-red-400';
  };

  // Determinar color de fondo del score
  const getScoreBgColor = (scoreValue) => {
    if (scoreValue >= 90) return 'bg-green-500';
    if (scoreValue >= 70) return 'bg-yellow-500';
    if (scoreValue >= 50) return 'bg-orange-500';
    return 'bg-red-500';
  };

  // Icono de compatibilidad basado en score
  const getCompatibilityIcon = (scoreValue) => {
    if (scoreValue >= 90) return '🟢';
    if (scoreValue >= 70) return '🟡';
    if (scoreValue >= 50) return '🟠';
    return '🔴';
  };

  // Texto de calidad basado en score
  const getQualityLabel = (scoreValue) => {
    if (scoreValue >= 90) return 'Excelente';
    if (scoreValue >= 70) return 'Buena';
    if (scoreValue >= 50) return 'Aceptable';
    return 'Débil';
  };

  // Determinar si es la mejor opción
  const isBestOption = rank === 1;

  // Badge component simple
  const Badge = ({ color, children }) => {
    const colorClasses = {
      green: 'bg-green-500/20 text-green-400 border-green-500/30',
      blue: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
      yellow: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
      purple: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
      gray: 'bg-gray-500/20 text-gray-400 border-gray-500/30'
    };

    return (
      <span className={`
        inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium
        border ${colorClasses[color] || colorClasses.gray}
      `}>
        {children}
      </span>
    );
  };

  return (
    <div className={`
      relative p-3 rounded-lg border transition-all duration-200
      ${isBestOption 
        ? 'border-yellow-500/50 bg-gradient-to-br from-yellow-500/10 to-yellow-600/5 shadow-lg shadow-yellow-500/10' 
        : 'border-gray-700 bg-gray-800 hover:border-gray-600 hover:bg-gray-750'
      }
      hover:scale-[1.02] cursor-pointer group
    `}>
      {/* Badge de ranking */}
      <div className={`
        absolute -top-2 -left-2 w-7 h-7 rounded-full flex items-center justify-center 
        text-xs font-bold border-2 shadow-md z-10
        ${getRankColor(rank)}
      `}>
        #{rank}
      </div>

      {/* Badge "Mejor Opción" para el #1 */}
      {isBestOption && (
        <div className="absolute -top-2 right-2 px-2 py-0.5 bg-yellow-500 text-black text-[10px] font-bold rounded-full shadow-md">
          ⭐ MEJOR
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between ml-5 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg" title={`Compatibilidad: ${getQualityLabel(score)}`}>
            {getCompatibilityIcon(score)}
          </span>
          <div className="flex flex-col">
            <span className="font-medium text-white text-sm">Bus {busId}</span>
            <span className="text-[10px] text-gray-500">Posición {position + 1}</span>
          </div>
        </div>
        
        {/* Score con barra de progreso */}
        <div className="flex flex-col items-end">
          <span className={`text-xl font-bold ${getScoreColor(score)}`}>
            {score}%
          </span>
          <span className="text-[10px] text-gray-500">{getQualityLabel(score)}</span>
        </div>
      </div>

      {/* Barra de progreso del score */}
      <div className="ml-5 mb-3">
        <div className="w-full h-1.5 bg-gray-700 rounded-full overflow-hidden">
          <div 
            className={`h-full rounded-full transition-all duration-500 ${getScoreBgColor(score)}`}
            style={{ width: `${score}%` }}
          />
        </div>
      </div>

      {/* Detalles */}
      <div className="ml-5 space-y-1.5 text-xs">
        <div className="flex items-center justify-between">
          <span className="text-gray-400 flex items-center gap-1.5">
            <span>⏱️</span> Inicio estimado:
          </span>
          <span className="text-white font-medium">{estimatedStartTime}</span>
        </div>

        {travelTimeFromPrev > 0 && (
          <div className="flex items-center justify-between">
            <span className="text-gray-400 flex items-center gap-1.5">
              <span>🚗</span> Viaje desde anterior:
            </span>
            <span className="text-white font-medium">{travelTimeFromPrev} min</span>
          </div>
        )}

        <div className="flex items-center justify-between">
          <span className="text-gray-400 flex items-center gap-1.5">
            <span>📊</span> Buffer disponible:
          </span>
          <span className={bufferTime > 10 ? 'text-green-400 font-medium' : 'text-yellow-400 font-medium'}>
            {bufferTime} min
          </span>
        </div>
      </div>

      {/* Factores/Indicadores */}
      <div className="ml-5 mt-3 flex flex-wrap gap-1.5">
        {factors.prev_buffer > 0.7 && (
          <Badge color="green">✓ Buen buffer anterior</Badge>
        )}
        {factors.prev_buffer > 0.9 && (
          <Badge color="green">✓ Buffer excelente</Badge>
        )}
        
        {factors.next_buffer > 0.7 && (
          <Badge color="blue">✓ Buen buffer siguiente</Badge>
        )}
        
        {factors.geographic_proximity > 0.7 && (
          <Badge color="purple">📍 Cerca geográficamente</Badge>
        )}
        
        {factors.time_alignment > 0.8 && (
          <Badge color="yellow">⏰ Alineación temporal perfecta</Badge>
        )}
        
        {factors.geographic_proximity < 0.3 && (
          <Badge color="gray">📍 Distancia considerable</Badge>
        )}
      </div>

      {/* Botón aplicar */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onApply?.();
        }}
        className={`
          w-full mt-3 py-2 rounded-lg font-medium text-sm transition-all duration-200
          flex items-center justify-center gap-2
          ${isBestOption 
            ? 'bg-yellow-500 hover:bg-yellow-400 text-black shadow-lg shadow-yellow-500/20 hover:shadow-yellow-500/30' 
            : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/20 hover:shadow-indigo-600/30'}
          active:scale-[0.98] transform
        `}
      >
        {isBestOption ? (
          <>
            <span>⭐</span>
            <span>Aplicar Mejor Opción</span>
          </>
        ) : (
          <>
            <span>✓</span>
            <span>Aplicar Sugerencia</span>
          </>
        )}
      </button>
    </div>
  );
}

export default SmartSuggestionCard;
