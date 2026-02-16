/**
 * Componente OptimizationProgress - UI de progreso de optimización
 * 
 * Muestra el progreso en tiempo real de la optimización conectada
 * al WebSocket del backend.
 * 
 * @module components/OptimizationProgress
 * @version 1.0.0
 */

import React, { useEffect, useRef } from 'react';
import { useOptimizationProgress } from '../hooks/useOptimizationProgress';
import { Loader2, CheckCircle, AlertCircle, Wifi, WifiOff } from 'lucide-react';
import { notifications } from '../services/notifications';

/**
 * Props del componente OptimizationProgress
 */
interface OptimizationProgressProps {
  /** ID del trabajo de optimización */
  jobId: string;
  /** Callback cuando se completa la optimización */
  onComplete?: (result: any) => void;
  /** Callback de progreso enriquecido */
  onProgress?: (state: {
    progress: number;
    phase: string;
    stage?: string;
    day?: string | null;
    iteration?: number | null;
    metrics?: Record<string, any> | null;
    message: string;
    stream?: string | null;
    engine?: string | null;
    optimizerPhase?: string | null;
    localProgress?: number | null;
  }) => void;
  /** Callback cuando ocurre un error */
  onError?: (error: string) => void;
  /** Clases CSS adicionales */
  className?: string;
}

const STAGE_LABELS: Record<string, string> = {
  queued: 'En cola de ejecución...',
  starting: 'Inicializando pipeline...',
  ingest: 'Ingesta y normalización de rutas...',
  baseline_optimize: 'Optimización base por día...',
  qubo_encode: 'Codificando subproblemas QUBO...',
  quantum_refine: 'Refinamiento híbrido quantum-inspired...',
  osrm_validate: 'Validación OSRM de solución base...',
  select_best: 'Seleccionando mejor solución...',
  improved: 'Se encontró una mejora...',
  no_improvement: 'Sin mejoras adicionales, cerrando iteración...',
  budget_reached: 'Se alcanzó el límite de tiempo...',
  completed: 'Pipeline completado',
  error: 'Error en el pipeline',
  idle: 'Esperando...',
  connecting: 'Conectando al backend...',
};

const STAGE_COLORS: Record<string, string> = {
  queued: 'bg-slate-500',
  starting: 'bg-blue-500',
  ingest: 'bg-cyan-500',
  baseline_optimize: 'bg-indigo-500',
  qubo_encode: 'bg-violet-500',
  quantum_refine: 'bg-fuchsia-500',
  osrm_validate: 'bg-emerald-500',
  select_best: 'bg-blue-500',
  improved: 'bg-emerald-500',
  no_improvement: 'bg-amber-500',
  budget_reached: 'bg-amber-500',
  completed: 'bg-green-500',
  error: 'bg-red-500',
  idle: 'bg-gray-400',
  connecting: 'bg-blue-400',
};

function resolveStageKey(stage?: string, phase?: string): string {
  const raw = (stage || phase || '').trim();
  if (!raw) return 'running';
  if (raw.startsWith('reoptimize_iter_')) return 'baseline_optimize';
  if (raw.startsWith('osrm_validate_iter_')) return 'osrm_validate';
  return raw;
}

function resolveStageLabel(stage?: string, phase?: string, fallback?: string): string {
  const key = resolveStageKey(stage, phase);
  return STAGE_LABELS[key] || fallback || key;
}

function resolveStageColor(stage?: string, phase?: string): string {
  const key = resolveStageKey(stage, phase);
  return STAGE_COLORS[key] || 'bg-blue-500';
}

function formatEventTime(timestamp?: string): string {
  if (!timestamp) return '--:--:--';
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return '--:--:--';
  return date.toLocaleTimeString('es-ES', { hour12: false });
}

/**
 * Componente de progreso de optimización con WebSocket
 * 
 * @example
 * ```tsx
 * <OptimizationProgress
 *   jobId="uuid-123"
 *   onComplete={(result) => setSchedule(result.schedule)}
 *   onError={(error) => console.error(error)}
 * />
 * ```
 */
export const OptimizationProgress: React.FC<OptimizationProgressProps> = ({
  jobId,
  onComplete,
  onProgress,
  onError,
  className = '',
}) => {
  const { progress, phase, stage, day, iteration, metrics, events, status, message, result, error } =
    useOptimizationProgress(jobId);

  const onCompleteRef = useRef(onComplete);
  const onProgressRef = useRef(onProgress);
  const onErrorRef = useRef(onError);
  const hasCompletedRef = useRef(false);
  const lastErrorRef = useRef<string | null>(null);
  const lastProgressSignatureRef = useRef('');

  useEffect(() => {
    onCompleteRef.current = onComplete;
    onProgressRef.current = onProgress;
    onErrorRef.current = onError;
  }, [onComplete, onProgress, onError]);

  useEffect(() => {
    hasCompletedRef.current = false;
    lastErrorRef.current = null;
    lastProgressSignatureRef.current = '';
  }, [jobId]);

  useEffect(() => {
    if (status === 'completed' && result && !hasCompletedRef.current) {
      hasCompletedRef.current = true;
      notifications.success('¡Optimización completada!', 'Los resultados están listos');
      onCompleteRef.current?.(result);
    }
  }, [status, result]);

  useEffect(() => {
    if (status === 'error' && error) {
      if (lastErrorRef.current === error) {
        return;
      }
      lastErrorRef.current = error;
      onErrorRef.current?.(error);
    }
  }, [status, error]);

  const metricsKey = (() => {
    if (!metrics) return '';
    try {
      return JSON.stringify(metrics);
    } catch {
      return '[metrics]';
    }
  })();

  const lastEvent = events.length > 0 ? events[events.length - 1] : null;

  useEffect(() => {
    const callback = onProgressRef.current;
    if (!callback || (status !== 'running' && status !== 'queued')) {
      return;
    }

    const signature = [
      status,
      `${Math.round(progress * 10) / 10}`,
      phase || '',
      stage || '',
      day || '',
      `${iteration ?? ''}`,
      message || '',
      metricsKey,
      lastEvent?.stream || '',
      lastEvent?.engine || '',
      lastEvent?.optimizerPhase || '',
      `${lastEvent?.localProgress ?? ''}`,
    ].join('|');

    if (signature === lastProgressSignatureRef.current) {
      return;
    }

    lastProgressSignatureRef.current = signature;
    callback({
        progress,
        phase,
        stage,
        day: day ?? null,
        iteration: iteration ?? null,
        metrics: metrics ?? null,
        message,
        stream: lastEvent?.stream ?? null,
        engine: lastEvent?.engine ?? null,
        optimizerPhase: lastEvent?.optimizerPhase ?? null,
        localProgress: lastEvent?.localProgress ?? null,
      });
  }, [status, progress, phase, stage, day, iteration, metrics, message, metricsKey, lastEvent]);

  // Estado de error
  if (status === 'error') {
    return (
      <div
        className={`
          w-full max-w-lg bg-red-500/[0.04] border border-red-500/[0.12] 
          rounded-xl p-5 animate-fadeIn ${className}
        `}
      >
        <div className="flex items-start gap-3">
          <div className="p-2 bg-red-500/[0.1] rounded-lg">
            <AlertCircle className="w-5 h-5 text-red-400" />
          </div>
          <div className="flex-1">
            <h3 className="font-medium text-red-400">
              Error en la optimización
            </h3>
            <p className="mt-1 text-sm text-red-300/80">{message}</p>
            {error && (
              <p className="mt-2 text-xs text-red-400/60 font-mono">
                Código: {error}
              </p>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Estado completado
  if (status === 'completed') {
    return (
      <div
        className={`
          w-full max-w-lg bg-emerald-500/[0.04] border border-emerald-500/[0.12] 
          rounded-xl p-5 animate-fadeIn ${className}
        `}
      >
        <div className="flex items-center gap-3">
          <div className="p-2 bg-emerald-500/[0.1] rounded-lg">
            <CheckCircle className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h3 className="font-medium text-emerald-400">
              Optimización completada
            </h3>
            <p className="text-sm text-emerald-300/80">
              Los resultados están listos para visualizar
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Estados: connecting, running, idle
  const isConnecting = status === 'connecting';
  const progressColor = resolveStageColor(stage, phase);
  const phaseLabel = resolveStageLabel(stage, phase, message || 'Procesando...');
  const recentEvents = events.slice(-12);

  return (
    <div
      className={`
        w-full max-w-lg bg-[#1c1c1f] border border-white/[0.06] 
        rounded-xl p-5 animate-fadeIn ${className}
      `}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div
            className={`
              p-2 rounded-lg transition-colors duration-300
              ${isConnecting ? 'bg-blue-500/[0.1]' : 'bg-indigo-500/[0.1]'}
            `}
          >
            {isConnecting ? (
              <Wifi className="w-5 h-5 text-blue-400 animate-pulse" />
            ) : (
              <Loader2 className="w-5 h-5 text-indigo-400 animate-spin" />
            )}
          </div>
          <div>
            <h3 className="font-medium text-white">
              {isConnecting ? 'Conectando...' : 'Optimizando rutas'}
            </h3>
            <p className="text-sm text-zinc-500">{phaseLabel}</p>
            {!isConnecting && (
              <div className="mt-1 flex items-center gap-2 text-[10px] font-mono text-zinc-500">
                <span className="px-1.5 py-0.5 rounded bg-white/[0.04] border border-white/[0.08]">
                  {stage || phase || 'running'}
                </span>
                {day && (
                  <span className="px-1.5 py-0.5 rounded bg-white/[0.04] border border-white/[0.08]">
                    Día {day}
                  </span>
                )}
                {iteration !== null && iteration !== undefined && (
                  <span className="px-1.5 py-0.5 rounded bg-white/[0.04] border border-white/[0.08]">
                    Iter {iteration}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
        <span className="text-2xl font-semibold text-white tabular-nums">
          {Math.round(progress)}%
        </span>
      </div>

      {/* Progress Bar */}
      <div className="relative">
        <div className="w-full bg-white/[0.06] rounded-full h-2.5 overflow-hidden">
          <div
            className={`
              h-full rounded-full transition-all duration-500 ease-out
              ${progressColor}
            `}
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Marcadores de progreso */}
        <div className="mt-3 flex justify-between text-[10px] text-zinc-600">
          <span>Ingesta</span>
          <span>Base</span>
          <span>Validación</span>
          <span>Final</span>
        </div>
      </div>

      {/* Información adicional */}
      {progress > 0 && progress < 100 && (
        <div className="mt-4 pt-4 border-t border-white/[0.04] space-y-2">
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <WifiOff className="w-3.5 h-3.5" />
            <span>Reconexión automática activada</span>
          </div>
          {metrics && (
            <div className="grid grid-cols-2 gap-1.5 text-[10px] font-mono text-zinc-400">
              {Object.entries(metrics).slice(0, 4).map(([key, value]) => (
                <div key={key} className="px-2 py-1 rounded bg-white/[0.03] border border-white/[0.06]">
                  <span className="text-zinc-500">{key}: </span>
                  <span className="text-zinc-300">{String(value)}</span>
                </div>
              ))}
            </div>
          )}
          {recentEvents.length > 0 && (
            <div className="mt-2">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] uppercase tracking-[0.1em] text-zinc-500">Bitacora backend</span>
                <span className="text-[10px] font-mono text-zinc-500">{recentEvents.length} eventos</span>
              </div>
              <div className="max-h-40 overflow-y-auto rounded-md border border-white/[0.06] bg-[#0b1118]">
                {recentEvents.map((evt, idx) => {
                  const isTrace = evt.stream === 'trace';
                  return (
                    <div
                      key={`${evt.phase}-${evt.stage}-${evt.timestamp || idx}`}
                      className={`px-2.5 py-1.5 border-b border-white/[0.04] text-[10px] font-mono ${isTrace ? 'text-zinc-300' : 'text-cyan-300'}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-zinc-500">{formatEventTime(evt.timestamp)}</span>
                        <span className="text-zinc-500">
                          {evt.day ? `Día ${evt.day}` : 'General'} · {Math.round(evt.progress)}%
                        </span>
                      </div>
                      <div className="mt-0.5">
                        <span className="text-cyan-200/90">[{evt.optimizerPhase || evt.stage || evt.phase}]</span>{' '}
                        <span>{evt.message}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default OptimizationProgress;
