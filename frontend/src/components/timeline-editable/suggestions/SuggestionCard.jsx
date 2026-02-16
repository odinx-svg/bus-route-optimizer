export function SuggestionCard({ suggestion, rank, onApply }) {
  const scorePercent = Math.round(suggestion.score * 100);
  
  // Determinar color del score
  const getScoreColor = (score) => {
    if (score >= 0.8) return 'text-green-400';
    if (score >= 0.6) return 'text-yellow-400';
    return 'text-gray-400';
  };
  
  // Determir color de la barra de progreso
  const getBarColor = (score) => {
    if (score >= 0.8) return 'bg-green-500';
    if (score >= 0.6) return 'bg-yellow-500';
    return 'bg-gray-500';
  };
  
  return (
    <div className="bg-gray-700 rounded p-2 border border-gray-600 hover:border-gray-500 transition-colors">
      {/* Header con rank y score */}
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className={`
            w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold
            ${rank === 1 ? 'bg-yellow-500/20 text-yellow-400' : 
              rank === 2 ? 'bg-gray-400/20 text-gray-300' : 
              rank === 3 ? 'bg-orange-600/20 text-orange-400' : 'bg-gray-600 text-gray-400'}
          `}>
            #{rank}
          </span>
          <span className="text-xs text-white font-medium">
            Bus {suggestion.busId}
          </span>
        </div>
        <span className={`text-xs font-bold ${getScoreColor(suggestion.score)}`}>
          {scorePercent}%
        </span>
      </div>
      
      {/* Barra de progreso del score */}
      <div className="w-full h-1 bg-gray-600 rounded-full mb-2">
        <div 
          className={`h-full rounded-full ${getBarColor(suggestion.score)}`}
          style={{ width: `${scorePercent}%` }}
        />
      </div>
      
      {/* Detalles de la sugerencia */}
      <div className="text-[10px] text-gray-400 space-y-0.5 mb-2">
        <div className="flex justify-between">
          <span>Inicio:</span>
          <span className="text-gray-300">{suggestion.startTime}</span>
        </div>
        <div className="flex justify-between">
          <span>Fin:</span>
          <span className="text-gray-300">{suggestion.endTime}</span>
        </div>
        {suggestion.gapAfter && (
          <div className="flex justify-between">
            <span>Gap siguiente:</span>
            <span className="text-gray-300">{suggestion.gapAfter} min</span>
          </div>
        )}
      </div>
      
      {/* Botón aplicar */}
      <button
        onClick={onApply}
        className="w-full py-1 px-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs rounded transition-colors"
      >
        Aplicar
      </button>
    </div>
  );
}
