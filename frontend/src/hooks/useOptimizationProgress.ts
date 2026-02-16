/**
 * Hook useOptimizationProgress - WebSocket para progreso de optimizacion
 *
 * Conecta al WebSocket del backend y gestiona el estado del progreso
 * en tiempo real con reconexion automatica.
 *
 * Incluye fallback de polling HTTP cuando el WebSocket no esta disponible.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { notifications } from '../services/notifications';

type MessageType = 'status' | 'progress' | 'completed' | 'error' | 'pong';

export interface ProgressState {
  progress: number;
  phase: string;
  status: 'idle' | 'connecting' | 'queued' | 'running' | 'completed' | 'error';
  message: string;
  stage?: string;
  day?: string | null;
  iteration?: number | null;
  metrics?: Record<string, any> | null;
  events: Array<{
    phase: string;
    stage?: string;
    progress: number;
    message: string;
    day?: string | null;
    iteration?: number | null;
    stream?: string | null;
    engine?: string | null;
    optimizerPhase?: string | null;
    localProgress?: number | null;
    timestamp?: string;
  }>;
  result?: any;
  error?: string;
}

interface StatusMessage {
  type: 'status';
  job_id: string;
  status: string;
  message: string;
  timestamp: string;
}

interface ProgressMessage {
  type: 'progress';
  job_id: string;
  phase: string;
  progress: number;
  message: string;
  stage?: string;
  day?: string | null;
  iteration?: number | null;
  metrics?: Record<string, any> | null;
  stream?: string | null;
  engine?: string | null;
  optimizer_phase?: string | null;
  local_progress?: number | null;
  timestamp: string;
}

interface CompletedMessage {
  type: 'completed';
  job_id: string;
  result: any;
  timestamp: string;
}

interface ErrorMessage {
  type: 'error';
  job_id: string;
  error_code: string;
  message: string;
  timestamp: string;
}

type WebSocketMessage =
  | StatusMessage
  | ProgressMessage
  | CompletedMessage
  | ErrorMessage
  | { type: 'pong' };

const INITIAL_STATE: ProgressState = {
  progress: 0,
  phase: '',
  status: 'idle',
  message: '',
  stage: '',
  day: null,
  iteration: null,
  metrics: null,
  events: [],
};

const resolveApiBaseUrl = (): string => {
  if (import.meta.env.VITE_API_URL) {
    return String(import.meta.env.VITE_API_URL).replace(/\/$/, '');
  }
  if (typeof window !== 'undefined') {
    const host = window.location.hostname === 'localhost' ? '127.0.0.1' : window.location.hostname;
    return `http://${host}:8000`;
  }
  return 'http://127.0.0.1:8000';
};

const resolveWsBaseUrl = (): string => {
  if (import.meta.env.VITE_WS_URL) {
    return String(import.meta.env.VITE_WS_URL).replace(/\/$/, '');
  }
  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host = window.location.hostname === 'localhost' ? '127.0.0.1' : window.location.hostname;
    return `${protocol}://${host}:8000`;
  }
  return 'ws://127.0.0.1:8000';
};

const checkBackendHealth = async (apiBaseUrl: string): Promise<boolean> => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(`${apiBaseUrl}/health`, {
      method: 'GET',
      signal: controller.signal,
    });
    return response.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timeout);
  }
};

export function useOptimizationProgress(jobId: string | null): ProgressState {
  const [state, setState] = useState<ProgressState>(INITIAL_STATE);

  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);
  const pollingTimer = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);
  const hasNotifiedPolling = useRef(false);
  const terminalStatus = useRef(false);
  const notFoundConsecutive = useRef(0);
  const networkFailureConsecutive = useRef(0);
  const unstableWarnModulo = useRef(0);
  const maxReconnectAttempts = 5;
  const maxNetworkFailureBeforeAbort = 200;

  const API_URL = resolveApiBaseUrl();
  const WS_URL = resolveWsBaseUrl();

  const stopPolling = useCallback(() => {
    if (pollingTimer.current) {
      clearTimeout(pollingTimer.current);
      pollingTimer.current = null;
    }
  }, []);

  const closeSocket = useCallback(() => {
    if (ws.current) {
      try {
        ws.current.close();
      } catch (err) {
        console.debug('[OptimizationWS] close failed', err);
      }
      ws.current = null;
    }
  }, []);

  const markCompleted = useCallback((result: any) => {
    terminalStatus.current = true;
    stopPolling();
    closeSocket();
    setState((prev) => ({
      ...prev,
      progress: 100,
      phase: 'completed',
      stage: 'completed',
      status: 'completed',
      message: 'Pipeline completado',
      result,
    }));
  }, [closeSocket, stopPolling]);

  const markError = useCallback((message: string, errorCode = 'PIPELINE_FAILED') => {
    terminalStatus.current = true;
    stopPolling();
    closeSocket();
    setState((prev) => ({
      ...prev,
      phase: 'error',
      stage: 'error',
      status: 'error',
      message,
      error: errorCode,
    }));
  }, [closeSocket, stopPolling]);

  const pollJobResult = useCallback(async () => {
    if (!jobId || terminalStatus.current) return;

    try {
      const fetchWithTimeout = async (url: string, timeoutMs = 10000) => {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), timeoutMs);
        try {
          return await fetch(url, { signal: controller.signal });
        } finally {
          clearTimeout(timeout);
        }
      };

      let resultWas404 = false;
      const resultResponse = await fetchWithTimeout(`${API_URL}/jobs/${jobId}/result`);
      if (resultResponse.status === 404) {
        resultWas404 = true;
      }
      if (resultResponse.ok) {
        networkFailureConsecutive.current = 0;
        notFoundConsecutive.current = 0;
        const resultData = await resultResponse.json();

        if (resultData.status === 'completed' && resultData.result) {
          markCompleted(resultData.result);
          return;
        }

        if (resultData.status === 'failed') {
          markError(resultData.error || 'Pipeline fallido', 'PIPELINE_FAILED');
          return;
        }

        if (resultData.status === 'cancelled') {
          markError('Pipeline cancelado por el usuario', 'PIPELINE_CANCELLED');
          return;
        }

        if (resultData.status === 'running' || resultData.status === 'queued') {
          setState((prev) => ({
            ...prev,
            status: resultData.status === 'queued' ? 'queued' : 'running',
            phase: resultData.status,
            stage: resultData.status,
            message: prev.message || `Pipeline ${resultData.status}...`,
          }));
          return;
        }
      }

      const statusResponse = await fetchWithTimeout(`${API_URL}/jobs/${jobId}`);
      if (!statusResponse.ok) {
        if (resultWas404 && statusResponse.status === 404) {
          notFoundConsecutive.current += 1;
          if (notFoundConsecutive.current >= 8) {
            markError(
              'Job no encontrado. Es posible que el backend se haya reiniciado. Lanza de nuevo la optimizacion.',
              'JOB_NOT_FOUND'
            );
          }
        }
        return;
      }

      networkFailureConsecutive.current = 0;
      notFoundConsecutive.current = 0;
      const statusData = await statusResponse.json();
      if (statusData.status === 'failed') {
        markError(statusData.error || 'Pipeline fallido', 'PIPELINE_FAILED');
      } else if (statusData.status === 'cancelled') {
        markError('Pipeline cancelado por el usuario', 'PIPELINE_CANCELLED');
      } else if (statusData.status === 'running' || statusData.status === 'queued') {
        setState((prev) => ({
          ...prev,
          status: statusData.status === 'queued' ? 'queued' : 'running',
          phase: statusData.status,
          stage: statusData.status,
          message: prev.message || `Pipeline ${statusData.status}...`,
        }));
      }
    } catch (err) {
      console.debug('[OptimizationPolling] Failed to poll job status', err);
      networkFailureConsecutive.current += 1;
      const failures = networkFailureConsecutive.current;
      setState((prev) => ({
        ...prev,
        status: prev.status === 'queued' ? 'queued' : 'running',
        message: `Conexion inestable con backend (${failures}). Reintentando...`,
      }));
      if (failures % 8 === 0 && unstableWarnModulo.current !== failures) {
        unstableWarnModulo.current = failures;
        notifications.warning(
          'Conexion inestable',
          'El backend sigue procesando. Reintentando obtener progreso.'
        );
      }
      if (networkFailureConsecutive.current >= maxNetworkFailureBeforeAbort) {
        markError(
          'No se pudo recuperar la conexion con backend durante un tiempo prolongado.',
          'NETWORK_UNSTABLE'
        );
      }
    }
  }, [API_URL, jobId, markCompleted, markError]);

  const startPolling = useCallback(() => {
    if (!jobId || pollingTimer.current || terminalStatus.current) return;

    if (!hasNotifiedPolling.current) {
      notifications.info(
        'Seguimiento alternativo activado',
        'WebSocket inestable. Se continua por consulta periodica.'
      );
      hasNotifiedPolling.current = true;
    }

    const scheduleNext = () => {
      if (terminalStatus.current) return;

      const failures = networkFailureConsecutive.current;
      const delayMs = failures <= 0
        ? 2000
        : Math.min(2000 + (failures * 1500), 30000);

      pollingTimer.current = setTimeout(async () => {
        pollingTimer.current = null;
        if (terminalStatus.current) return;
        await pollJobResult();
        if (!terminalStatus.current) {
          scheduleNext();
        }
      }, delayMs);
    };

    pollJobResult().finally(scheduleNext);
  }, [jobId, pollJobResult]);

  const connect = useCallback(async () => {
    if (!jobId) return;

    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
      reconnectTimeout.current = null;
    }

    const wsUrl = `${WS_URL}/ws/optimize/${jobId}`;
    setState((prev) => ({ ...prev, status: prev.status === 'completed' ? prev.status : 'connecting' }));

    try {
      const backendReady = await checkBackendHealth(API_URL);
      if (!backendReady) {
        setState((prev) => ({
          ...prev,
          status: prev.status === 'queued' ? 'queued' : 'running',
          message: 'Backend ocupado; esperando disponibilidad para stream en vivo...',
        }));
        reconnectAttempts.current += 1;
        const delay = Math.min(900 * Math.pow(2, reconnectAttempts.current), 15000);
        const jitter = Math.floor(Math.random() * 500);
        reconnectTimeout.current = setTimeout(() => {
          connect();
        }, delay + jitter);
        return;
      }

      ws.current = new WebSocket(wsUrl);

      ws.current.onopen = () => {
        reconnectAttempts.current = 0;
        notFoundConsecutive.current = 0;
        hasNotifiedPolling.current = false;
        stopPolling();
        setState((prev) => ({
          ...prev,
          status: prev.status === 'queued' ? 'queued' : 'running',
          message: prev.message || 'Conectado al pipeline',
        }));
      };

      ws.current.onmessage = (event: MessageEvent) => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data);

          switch (data.type as MessageType) {
            case 'status': {
              const statusRaw = data.status || 'running';
              if (statusRaw === 'completed') {
                pollJobResult();
                return;
              }
              if (statusRaw === 'failed') {
                markError(data.message || 'Pipeline fallido', 'PIPELINE_FAILED');
                return;
              }
              if (statusRaw === 'cancelled') {
                markError('Pipeline cancelado por el usuario', 'PIPELINE_CANCELLED');
                return;
              }
              setState((prev) => ({
                ...prev,
                status: statusRaw === 'queued' ? 'queued' : 'running',
                phase: statusRaw,
                stage: statusRaw,
                message: data.message || prev.message,
              }));
              break;
            }

            case 'progress': {
              setState((prev) => {
                const nextEvent = {
                  phase: data.phase,
                  stage: (data as any).stage || data.phase,
                  progress: data.progress,
                  message: data.message,
                  day: (data as any).day ?? null,
                  iteration: (data as any).iteration ?? null,
                  stream: (data as any).stream ?? null,
                  engine: (data as any).engine ?? null,
                  optimizerPhase: (data as any).optimizer_phase ?? null,
                  localProgress: (data as any).local_progress ?? null,
                  timestamp: (data as any).timestamp,
                };
                const events = [...prev.events, nextEvent].slice(-120);

                return {
                  ...prev,
                  progress: data.progress,
                  phase: data.phase,
                  stage: (data as any).stage || data.phase,
                  day: (data as any).day ?? null,
                  iteration: (data as any).iteration ?? null,
                  metrics: (data as any).metrics ?? prev.metrics ?? null,
                  status: 'running',
                  message: data.message,
                  events,
                };
              });
              break;
            }

            case 'completed':
              markCompleted(data.result);
              break;

            case 'error':
              markError(data.message || 'Error de pipeline', data.error_code || 'PIPELINE_FAILED');
              break;

            case 'pong':
              break;

            default:
              console.warn('[OptimizationWS] Unknown message type:', data);
          }
        } catch (err) {
          console.error('[OptimizationWS] Error parsing message:', err);
        }
      };

      ws.current.onerror = (error: Event) => {
        console.debug('[OptimizationWS] Socket error event', error);
        setState((prev) => ({
          ...prev,
          status: prev.status === 'completed' ? prev.status : 'running',
          message: prev.message || 'Conexion WS inestable; intentando recuperacion',
        }));
        startPolling();
      };

      ws.current.onclose = (event: CloseEvent) => {
        if (terminalStatus.current) return;

        if (!event.wasClean && reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current += 1;
          const delay = Math.min(1200 * Math.pow(2, reconnectAttempts.current), 15000);
          const jitter = Math.floor(Math.random() * 500);

          reconnectTimeout.current = setTimeout(() => {
            notifications.info(
              'Reconectando progreso',
              `Intento ${reconnectAttempts.current}/${maxReconnectAttempts}`
            );
            connect();
          }, delay + jitter);
          return;
        }

        startPolling();
      };
    } catch (err) {
      console.error('[OptimizationWS] Error creating WebSocket:', err);
      startPolling();
      setState((prev) => ({
        ...prev,
        status: 'running',
        message: 'No se pudo abrir WebSocket; usando fallback de polling',
      }));
    }
  }, [API_URL, WS_URL, jobId, markCompleted, markError, pollJobResult, startPolling, stopPolling]);

  useEffect(() => {
    setState(INITIAL_STATE);
    hasNotifiedPolling.current = false;
    reconnectAttempts.current = 0;
    notFoundConsecutive.current = 0;
    networkFailureConsecutive.current = 0;
    unstableWarnModulo.current = 0;
    terminalStatus.current = false;
  }, [jobId]);

  useEffect(() => {
    if (!jobId) return;

    connect();

    const heartbeat = setInterval(() => {
      if (ws.current?.readyState === WebSocket.OPEN) {
        ws.current.send(JSON.stringify({ action: 'ping' }));
      }
    }, 30000);

    return () => {
      terminalStatus.current = true;
      clearInterval(heartbeat);
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
        reconnectTimeout.current = null;
      }
      stopPolling();
      closeSocket();
    };
  }, [closeSocket, connect, jobId, stopPolling]);

  return state;
}

export default useOptimizationProgress;
