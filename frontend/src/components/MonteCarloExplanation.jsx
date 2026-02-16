import { Play, Info, Shield, AlertTriangle } from 'lucide-react';

export function MonteCarloExplanation({ onStart, disabled }) {
  return (
    <div className="bg-gray-800 p-6 rounded-lg">
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 bg-blue-600 rounded-lg">
          <Shield className="w-6 h-6 text-white" />
        </div>
        <h3 className="text-xl font-bold text-white">
          ¿Qué es la Validación Monte Carlo?
        </h3>
      </div>
      
      <div className="space-y-4 text-gray-300">
        <p className="text-base leading-relaxed">
          Monte Carlo simula tu horario <strong className="text-white">hasta 10,000 veces</strong> con variaciones 
          realistas de tráfico (atascos, retrasos, imprevistos) para verificar si tu horario es 
          <span className="text-green-400 font-semibold"> robusto</span>.
        </p>
        
        <div className="bg-gray-900 p-4 rounded-lg border border-gray-700">
          <h4 className="font-semibold text-white mb-3 flex items-center gap-2">
            <Info className="w-4 h-4 text-blue-400" />
            ¿Qué evaluamos?
          </h4>
          <ul className="space-y-2 text-sm">
            <li className="flex items-start gap-2">
              <span className="text-green-400 mt-0.5">✓</span>
              <span>¿Los buses llegan a tiempo aunque haya tráfico?</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-400 mt-0.5">✓</span>
              <span>¿Hay tiempo suficiente entre rutas consecutivas?</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-green-400 mt-0.5">✓</span>
              <span>¿El horario es robusto o se rompe fácilmente?</span>
            </li>
          </ul>
        </div>
        
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-green-900/30 p-4 rounded-lg border border-green-700/50">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-3 h-3 rounded-full bg-green-400"></div>
              <span className="text-green-400 font-bold">Puntos Verdes</span>
            </div>
            <p className="text-sm text-gray-300">
              Escenarios donde el horario funciona bien sin problemas
            </p>
          </div>
          <div className="bg-red-900/30 p-4 rounded-lg border border-red-700/50">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-3 h-3 rounded-full bg-red-400"></div>
              <span className="text-red-400 font-bold">Puntos Rojos</span>
            </div>
            <p className="text-sm text-gray-300">
              Escenarios con conflictos (llegadas tarde, superposiciones)
            </p>
          </div>
        </div>
        
        <div className="bg-blue-900/20 p-4 rounded-lg border border-blue-700/30">
          <h4 className="font-semibold text-white mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-blue-400" />
            Grados de Robustez
          </h4>
          <div className="grid grid-cols-5 gap-2 text-center text-sm">
            <div className="bg-gray-900 p-2 rounded">
              <span className="text-green-400 font-bold text-lg">A</span>
              <p className="text-xs text-gray-400 mt-1">95%+</p>
              <p className="text-xs text-green-400">Excelente</p>
            </div>
            <div className="bg-gray-900 p-2 rounded">
              <span className="text-green-300 font-bold text-lg">B</span>
              <p className="text-xs text-gray-400 mt-1">85-95%</p>
              <p className="text-xs text-green-300">Bueno</p>
            </div>
            <div className="bg-gray-900 p-2 rounded">
              <span className="text-yellow-400 font-bold text-lg">C</span>
              <p className="text-xs text-gray-400 mt-1">70-85%</p>
              <p className="text-xs text-yellow-400">Aceptable</p>
            </div>
            <div className="bg-gray-900 p-2 rounded">
              <span className="text-orange-400 font-bold text-lg">D</span>
              <p className="text-xs text-gray-400 mt-1">50-70%</p>
              <p className="text-xs text-orange-400">Débil</p>
            </div>
            <div className="bg-gray-900 p-2 rounded">
              <span className="text-red-400 font-bold text-lg">F</span>
              <p className="text-xs text-gray-400 mt-1">&lt;50%</p>
              <p className="text-xs text-red-400">No viable</p>
            </div>
          </div>
        </div>
      </div>
      
      <button 
        onClick={onStart}
        disabled={disabled}
        className="mt-6 w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 
                   disabled:text-gray-500 disabled:cursor-not-allowed text-white rounded-lg 
                   font-semibold flex items-center justify-center gap-2 transition-colors"
      >
        <Play className="w-5 h-5" />
        {disabled 
          ? 'Primero optimiza un horario' 
          : 'Iniciar Validación Monte Carlo'}
      </button>
      
      {disabled && (
        <p className="mt-2 text-center text-sm text-gray-500">
          Debes optimizar un horario antes de poder validarlo
        </p>
      )}
    </div>
  );
}
