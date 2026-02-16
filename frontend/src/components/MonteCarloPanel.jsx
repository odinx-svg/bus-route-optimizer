import { useState } from 'react';
import { MonteCarlo3D } from './MonteCarlo3D';
import { MonteCarloExplanation } from './MonteCarloExplanation';
import { MonteCarloResults } from './MonteCarloResults';
import { useMonteCarlo3D } from '../hooks/useMonteCarlo3D';
import { Play, Square, Settings2, RotateCcw, CheckCircle, Zap, Target, Trophy } from 'lucide-react';

export function MonteCarloPanel({ schedule, hasOptimizedSchedule = false }) {
  const [config, setConfig] = useState({
    n_simulations: 10000,
    uncertainty: 0.2
  });
  const [showConfig, setShowConfig] = useState(false);
  const [showExplanation, setShowExplanation] = useState(true);
  
  const {
    scenarios,
    progress,
    grade,
    status,
    startSimulation,
    stopSimulation
  } = useMonteCarlo3D(schedule);

  // Determinar si hay resultados para mostrar
  const hasResults = status === 'completed' && grade !== null;
  
  // Calcular estadísticas
  const stats = progress ? {
    total: progress.total,
    feasible: Math.round(progress.total * progress.feasible_rate),
    infeasible: Math.round(progress.total * (1 - progress.feasible_rate)),
    feasibleRate: progress.feasible_rate
  } : null;

  // Calcular tiempo estimado según número de simulaciones
  const getEstimatedTime = (n) => {
    if (n <= 1000) return '≈ 10 segundos';
    if (n <= 10000) return '≈ 2 minutos';
    return '≈ 10 minutos';
  };

  // Opciones rápidas de simulación
  const quickOptions = [
    { value: 1000, label: '1,000', icon: Zap, desc: 'Rápido', time: '≈ 10s' },
    { value: 10000, label: '10,000', icon: Target, desc: 'Recomendado', time: '≈ 2min' },
    { value: 50000, label: '50,000', icon: Trophy, desc: 'Preciso', time: '≈ 10min' }
  ];

  const handleStart = () => {
    setShowExplanation(false);
    startSimulation(config);
  };

  const handleReset = () => {
    setShowExplanation(true);
  };

  const handleQuickSelect = (value) => {
    setConfig({ ...config, n_simulations: value });
  };

  return (
    <div className="bg-gray-900 rounded-lg p-6 h-full overflow-y-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-bold text-white">
            Validación Monte Carlo 3D
          </h2>
          {hasResults && (
            <span className={`px-2 py-1 rounded text-sm font-bold ${
              grade === 'A' ? 'bg-green-400/20 text-green-400' :
              grade === 'B' ? 'bg-green-300/20 text-green-300' :
              grade === 'C' ? 'bg-yellow-400/20 text-yellow-400' :
              grade === 'D' ? 'bg-orange-400/20 text-orange-400' :
              'bg-red-400/20 text-red-400'
            }`}>
              Grado {grade}
            </span>
          )}
        </div>
        
        <div className="flex gap-2">
          {/* Botón de configuración */}
          <button
            onClick={() => setShowConfig(!showConfig)}
            className={`p-2 rounded transition-colors ${
              showConfig 
                ? 'bg-blue-600 text-white' 
                : 'bg-gray-700 text-white hover:bg-gray-600'
            }`}
            disabled={status === 'running'}
          >
            <Settings2 className="w-5 h-5" />
          </button>
          
          {/* Botón de reinicio (solo cuando hay resultados) */}
          {hasResults && (
            <button
              onClick={handleReset}
              className="flex items-center gap-2 px-4 py-2 rounded bg-gray-700 text-white hover:bg-gray-600"
            >
              <RotateCcw className="w-4 h-4" />
              Ver Explicación
            </button>
          )}
          
          {/* Botones de control de simulación */}
          {status === 'running' ? (
            <button
              onClick={stopSimulation}
              className="flex items-center gap-2 px-4 py-2 rounded bg-red-600 text-white hover:bg-red-700"
            >
              <Square className="w-4 h-4" />
              Detener
            </button>
          ) : (
            <button
              onClick={handleStart}
              disabled={!hasOptimizedSchedule || showExplanation}
              className="flex items-center gap-2 px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Play className="w-4 h-4" />
              Iniciar Simulación
            </button>
          )}
        </div>
      </div>

      {/* Panel de configuración */}
      {showConfig && (
        <div className="mb-6 p-4 bg-gray-800 rounded-lg">
          <h4 className="text-sm font-semibold text-white mb-3">Configuración de Simulación</h4>
          
          {/* Opciones rápidas */}
          <div className="mb-4">
            <label className="block text-xs text-gray-500 mb-2">Opciones rápidas</label>
            <div className="grid grid-cols-3 gap-2">
              {quickOptions.map((option) => {
                const Icon = option.icon;
                const isSelected = config.n_simulations === option.value;
                return (
                  <button
                    key={option.value}
                    onClick={() => handleQuickSelect(option.value)}
                    disabled={status === 'running'}
                    className={`flex flex-col items-center p-3 rounded-lg border transition-all ${
                      isSelected
                        ? 'bg-blue-600/20 border-blue-500 text-blue-400'
                        : 'bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600'
                    } disabled:opacity-50`}
                  >
                    <Icon className="w-4 h-4 mb-1" />
                    <span className="text-sm font-medium">{option.label}</span>
                    <span className="text-xs opacity-70">{option.desc}</span>
                    <span className="text-xs text-gray-500 mt-1">{option.time}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Número de Simulaciones
              </label>
              <input
                type="number"
                value={config.n_simulations}
                onChange={(e) => setConfig({...config, n_simulations: parseInt(e.target.value)})}
                className="w-full px-3 py-2 bg-gray-700 rounded text-white"
                min="1000"
                max="100000"
                step="1000"
                disabled={status === 'running'}
              />
              <p className="text-xs text-gray-500 mt-1">
                Más simulaciones = mayor precisión
              </p>
              <p className="text-xs text-blue-400 mt-1">
                Tiempo estimado: {getEstimatedTime(config.n_simulations)}
              </p>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Nivel de Incertidumbre ({(config.uncertainty * 100).toFixed(0)}%)
              </label>
              <input
                type="range"
                value={config.uncertainty}
                onChange={(e) => setConfig({...config, uncertainty: parseFloat(e.target.value)})}
                className="w-full"
                min="0.05"
                max="0.5"
                step="0.05"
                disabled={status === 'running'}
              />
              <p className="text-xs text-gray-500 mt-1">Variabilidad del tráfico simulado</p>
            </div>
          </div>
        </div>
      )}

      {/* Panel explicativo - se muestra al inicio o cuando se reinicia */}
      {showExplanation && status === 'idle' && (
        <MonteCarloExplanation 
          onStart={handleStart}
          disabled={!hasOptimizedSchedule}
        />
      )}

      {/* Estado de simulación en progreso */}
      {status === 'running' && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-white font-medium">Simulando escenarios...</span>
            <span className="text-blue-400">
              {progress?.completed || 0} / {progress?.total || config.n_simulations}
            </span>
          </div>
          <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
            <div 
              className="h-full bg-blue-500 rounded-full transition-all duration-300"
              style={{ 
                width: `${((progress?.completed || 0) / (progress?.total || config.n_simulations)) * 100}%` 
              }}
            />
          </div>
          {grade && (
            <div className="mt-3 flex items-center gap-2 text-sm">
              <span className="text-gray-400">Grado actual:</span>
              <span className={`font-bold ${
                grade === 'A' ? 'text-green-400' :
                grade === 'B' ? 'text-green-300' :
                grade === 'C' ? 'text-yellow-400' :
                grade === 'D' ? 'text-orange-400' :
                'text-red-400'
              }`}>{grade}</span>
            </div>
          )}
        </div>
      )}

      {/* Visualización 3D - muestra durante y después de la simulación */}
      {(status === 'running' || scenarios.length > 0) && (
        <MonteCarlo3D
          scenarios={scenarios}
          progress={progress}
          grade={grade}
        />
      )}

      {/* Resultados detallados - solo al completar */}
      {hasResults && stats && (
        <div className="mt-6">
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle className="w-5 h-5 text-green-400" />
            <h3 className="text-lg font-semibold text-white">Resultados de la Validación</h3>
          </div>
          <MonteCarloResults 
            grade={grade}
            feasibleRate={stats.feasibleRate}
            stats={stats}
          />
        </div>
      )}

      {/* Mensaje cuando no hay horario optimizado */}
      {!hasOptimizedSchedule && status === 'idle' && !showExplanation && (
        <div className="h-[300px] flex items-center justify-center text-gray-500 bg-gray-800/50 rounded-lg border border-dashed border-gray-700">
          <div className="text-center">
            <Settings2 className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p className="text-gray-400">No hay horario optimizado</p>
            <p className="text-sm mt-1">Ve a la pestaña "Optimizar" primero</p>
          </div>
        </div>
      )}
    </div>
  );
}
