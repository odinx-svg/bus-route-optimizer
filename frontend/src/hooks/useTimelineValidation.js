/**
 * Hook React para validación de timeline vía WebSocket.
 * 
 * Proporciona:
 * - Conexión WebSocket persistente
 * - Validación de compatibilidad entre rutas
 * - Sugerencias de ubicación
 * - Estados de carga y error
 * - Cache de resultados
 * 
 * @example
 * const { checkCompatibility, getSuggestions, isConnected, isValidating } = useTimelineValidation();
 * 
 * const result = await checkCompatibility(routeA, routeB);
 * if (result.is_compatible) {
 *   // La ruta puede moverse aquí
 * }
 */

import { useState, useEffect, useRef, useCallback } from 'react';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';
const WS_ENDPOINT = '/ws/timeline-validate';
const RECONNECT_DELAY = 3000;
const MAX_RECONNECT_ATTEMPTS = 5;

/**
 * @typedef {Object} CompatibilityResult
 * @property {boolean} is_compatible - Si las rutas son compatibles
 * @property {number} travel_time_minutes - Tiempo de viaje calculado
 * @property {number} buffer_minutes - Margen disponible en minutos
 * @property {number} time_available - Tiempo disponible entre rutas
 * @property {'excellent'|'good'|'tight'|'incompatible'} quality - Calidad de compatibilidad
 * @property {boolean} from_fallback - Si se usó fallback (OSRM no disponible)
 * @property {string} [error] - Mensaje de error si hubo problema
 * @property {string} [warning] - Advertencia si se usó fallback
 * @property {number} validation_time_ms - Tiempo de validación
 */

/**
 * @typedef {Object} Suggestion
 * @property {string} bus_id - ID del bus
 * @property {number} position - Posición sugerida
 * @property {number} score - Puntaje (0-100)
 * @property {string[]} reasons - Razones de la sugerencia
 * @property {number} current_routes_count - Número actual de rutas
 */

/**
 * Hook para validación de timeline en tiempo real.
 * @returns {Object} Estado y funciones del WebSocket
 */
export function useTimelineValidation() {
  const [isConnected, setIsConnected] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState(null);
  
  const wsRef = useRef(null);
  const pendingRequestsRef = useRef(new Map());
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef(null);
  const requestIdCounterRef = useRef(0);
  
  // Cache local de resultados
  const cacheRef = useRef(new Map());
  const CACHE_TTL = 5 * 60 * 1000; // 5 minutos

  /**
   * Genera un ID único para requests.
   */
  const generateRequestId = useCallback(() => {
    requestIdCounterRef.current += 1;
    return `req_${Date.now()}_${requestIdCounterRef.current}`;
  }, []);

  /**
   * Genera una clave de cache para un par de rutas.
   */
  const getCacheKey = useCallback((routeA, routeB) => {
    const coordsA = routeA.endCoordinates || routeA.end_location;
    const coordsB = routeB.startCoordinates || routeB.start_location;
    const timeA = routeA.endTime || routeA.end_time;
    const timeB = routeB.startTime || routeB.start_time;
    return `${JSON.stringify(coordsA)}|${JSON.stringify(coordsB)}|${timeA}|${timeB}`;
  }, []);

  /**
   * Limpia entradas expiradas del cache.
   */
  const clearExpiredCache = useCallback(() => {
    const now = Date.now();
    for (const [key, entry] of cacheRef.current.entries()) {
      if (now - entry.timestamp > CACHE_TTL) {
        cacheRef.current.delete(key);
      }
    }
  }, []);

  /**
   * Conecta al WebSocket.
   */
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      const ws = new WebSocket(`${WS_URL}${WS_ENDPOINT}`);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[TimelineValidation WS] Connected');
        setIsConnected(true);
        setError(null);
        reconnectAttemptsRef.current = 0;
      };

      ws.onclose = (event) => {
        console.log('[TimelineValidation WS] Disconnected:', event.code, event.reason);
        setIsConnected(false);
        wsRef.current = null;

        // Reintentar conexión si no fue cerrado intencionalmente
        if (event.code !== 1000 && event.code !== 1001) {
          if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
            reconnectAttemptsRef.current += 1;
            console.log(`[TimelineValidation WS] Reconnecting in ${RECONNECT_DELAY}ms (attempt ${reconnectAttemptsRef.current})`);
            reconnectTimeoutRef.current = setTimeout(connect, RECONNECT_DELAY);
          } else {
            setError('No se pudo reconectar al servidor de validación');
          }
        }
      };

      ws.onerror = (error) => {
        console.error('[TimelineValidation WS] Error:', error);
        setError('Error de conexión con el servidor');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleMessage(data);
        } catch (e) {
          console.error('[TimelineValidation WS] Error parsing message:', e);
        }
      };

    } catch (e) {
      console.error('[TimelineValidation WS] Connection error:', e);
      setError('Error al conectar con el servidor');
    }
  }, []);

  /**
   * Maneja mensajes recibidos del WebSocket.
   */
  const handleMessage = useCallback((data) => {
    const { type, request_id: requestId } = data;

    switch (type) {
      case 'connected':
        console.log('[TimelineValidation WS] Session:', data.session_id);
        break;

      case 'compatibility_result':
      case 'suggestions':
      case 'batch_results':
        // Resolver pending request
        const pending = pendingRequestsRef.current.get(requestId);
        if (pending) {
          pending.resolve(data);
          pendingRequestsRef.current.delete(requestId);
          
          // Guardar en cache si es resultado de compatibilidad
          if (type === 'compatibility_result' && pending.cacheKey) {
            cacheRef.current.set(pending.cacheKey, {
              data,
              timestamp: Date.now()
            });
          }
        }
        setIsValidating(false);
        break;

      case 'validating':
      case 'calculating_suggestions':
      case 'batch_validating':
        // Indicadores de progreso - opcionalmente podríamos exponerlos
        console.log('[TimelineValidation WS]', data.message);
        break;

      case 'batch_progress':
        // Progreso de validación batch
        console.log(`[TimelineValidation WS] Progress: ${data.completed}/${data.total}`);
        break;

      case 'error':
        // Error del servidor
        const errorPending = pendingRequestsRef.current.get(requestId);
        if (errorPending) {
          errorPending.reject(new Error(data.error));
          pendingRequestsRef.current.delete(requestId);
        } else {
          setError(data.error);
        }
        setIsValidating(false);
        break;

      case 'stats':
        setStats(data.stats);
        break;

      case 'pong':
        // Heartbeat response
        break;

      default:
        console.log('[TimelineValidation WS] Unknown message type:', type, data);
    }
  }, []);

  /**
   * Envía un mensaje al WebSocket.
   */
  const sendMessage = useCallback((message) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
      return true;
    }
    return false;
  }, []);

  /**
   * Verifica la compatibilidad entre dos rutas.
   * @param {Object} routeA - Ruta A (con endCoordinates y endTime)
   * @param {Object} routeB - Ruta B (con startCoordinates y startTime)
   * @param {Object} options - Opciones
   * @param {boolean} options.skipCache - Saltar cache
   * @returns {Promise<CompatibilityResult>} Resultado de compatibilidad
   * @example
   * const result = await checkCompatibility(
   *   { endCoordinates: [lat, lon], endTime: '08:30' },
   *   { startCoordinates: [lat, lon], startTime: '09:00' }
   * );
   */
  const checkCompatibility = useCallback(async (routeA, routeB, options = {}) => {
    if (!routeA || !routeB) {
      throw new Error('Se requieren routeA y routeB');
    }

    const cacheKey = getCacheKey(routeA, routeB);
    
    // Verificar cache
    if (!options.skipCache) {
      clearExpiredCache();
      const cached = cacheRef.current.get(cacheKey);
      if (cached) {
        console.log('[TimelineValidation] Cache hit');
        return cached.data;
      }
    }

    // Asegurar conexión
    if (!isConnected) {
      await new Promise((resolve, reject) => {
        const checkConnection = () => {
          if (isConnected) {
            resolve();
          } else if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
            reject(new Error('No hay conexión con el servidor'));
          } else {
            setTimeout(checkConnection, 100);
          }
        };
        checkConnection();
      });
    }

    const requestId = generateRequestId();

    return new Promise((resolve, reject) => {
      // Guardar pending request
      pendingRequestsRef.current.set(requestId, { 
        resolve, 
        reject, 
        cacheKey: options.skipCache ? null : cacheKey 
      });

      setIsValidating(true);
      setError(null);

      // Enviar mensaje
      const sent = sendMessage({
        type: 'check_compatibility',
        request_id: requestId,
        route_a: routeA,
        route_b: routeB
      });

      if (!sent) {
        pendingRequestsRef.current.delete(requestId);
        setIsValidating(false);
        reject(new Error('No se pudo enviar el mensaje'));
      }

      // Timeout de 10 segundos
      setTimeout(() => {
        if (pendingRequestsRef.current.has(requestId)) {
          pendingRequestsRef.current.delete(requestId);
          setIsValidating(false);
          reject(new Error('Timeout esperando respuesta'));
        }
      }, 10000);
    });
  }, [isConnected, generateRequestId, getCacheKey, clearExpiredCache, sendMessage]);

  /**
   * Obtiene sugerencias para ubicar una ruta.
   * @param {Object} route - Ruta a ubicar
   * @param {Array} buses - Lista de buses disponibles
   * @returns {Promise<{suggestions: Suggestion[], calculation_time_ms: number}>}
   * @example
   * const { suggestions } = await getSuggestions(
   *   { startCoordinates: [lat, lon], endCoordinates: [lat, lon], startTime: '09:00', endTime: '09:30' },
   *   [{ busId: 'B1', routes: [...] }, { busId: 'B2', routes: [...] }]
   * );
   */
  const getSuggestions = useCallback(async (route, buses) => {
    if (!route || !buses || !Array.isArray(buses)) {
      throw new Error('Se requieren route y buses array');
    }

    if (!isConnected) {
      throw new Error('No hay conexión con el servidor');
    }

    const requestId = generateRequestId();

    return new Promise((resolve, reject) => {
      pendingRequestsRef.current.set(requestId, { resolve, reject });

      setIsValidating(true);
      setError(null);

      const sent = sendMessage({
        type: 'get_suggestions',
        request_id: requestId,
        route,
        buses
      });

      if (!sent) {
        pendingRequestsRef.current.delete(requestId);
        setIsValidating(false);
        reject(new Error('No se pudo enviar el mensaje'));
      }

      setTimeout(() => {
        if (pendingRequestsRef.current.has(requestId)) {
          pendingRequestsRef.current.delete(requestId);
          setIsValidating(false);
          reject(new Error('Timeout esperando sugerencias'));
        }
      }, 15000);
    });
  }, [isConnected, generateRequestId, sendMessage]);

  /**
   * Valida múltiples pares de rutas en batch.
   * @param {Array} pairs - Pares de rutas a validar
   * @returns {Promise<{results: Array, validation_time_ms: number}>}
   * @example
   * const { results } = await batchValidate([
   *   { id: '1', route_a: {...}, route_b: {...} },
   *   { id: '2', route_a: {...}, route_b: {...} }
   * ]);
   */
  const batchValidate = useCallback(async (pairs) => {
    if (!pairs || !Array.isArray(pairs)) {
      throw new Error('Se requiere array de pares');
    }

    if (!isConnected) {
      throw new Error('No hay conexión con el servidor');
    }

    const requestId = generateRequestId();

    return new Promise((resolve, reject) => {
      pendingRequestsRef.current.set(requestId, { resolve, reject });

      setIsValidating(true);
      setError(null);

      const sent = sendMessage({
        type: 'batch_validate',
        request_id: requestId,
        pairs
      });

      if (!sent) {
        pendingRequestsRef.current.delete(requestId);
        setIsValidating(false);
        reject(new Error('No se pudo enviar el mensaje'));
      }

      setTimeout(() => {
        if (pendingRequestsRef.current.has(requestId)) {
          pendingRequestsRef.current.delete(requestId);
          setIsValidating(false);
          reject(new Error('Timeout en validación batch'));
        }
      }, 30000);
    });
  }, [isConnected, generateRequestId, sendMessage]);

  /**
   * Obtiene estadísticas del servidor.
   * @returns {Promise<Object>}
   */
  const getStats = useCallback(async () => {
    if (!isConnected) {
      throw new Error('No hay conexión con el servidor');
    }

    const requestId = generateRequestId();

    return new Promise((resolve, reject) => {
      pendingRequestsRef.current.set(requestId, { resolve, reject });

      const sent = sendMessage({
        type: 'get_stats',
        request_id: requestId
      });

      if (!sent) {
        pendingRequestsRef.current.delete(requestId);
        reject(new Error('No se pudo enviar el mensaje'));
      }

      setTimeout(() => {
        if (pendingRequestsRef.current.has(requestId)) {
          pendingRequestsRef.current.delete(requestId);
          reject(new Error('Timeout esperando stats'));
        }
      }, 5000);
    });
  }, [isConnected, generateRequestId, sendMessage]);

  /**
   * Limpia el cache local.
   */
  const clearCache = useCallback(() => {
    cacheRef.current.clear();
    console.log('[TimelineValidation] Cache cleared');
  }, []);

  /**
   * Envía un heartbeat para mantener la conexión viva.
   */
  const ping = useCallback(() => {
    sendMessage({ type: 'ping' });
  }, [sendMessage]);

  // Conectar al montar
  useEffect(() => {
    connect();

    // Heartbeat cada 30 segundos
    const heartbeatInterval = setInterval(ping, 30000);

    return () => {
      clearInterval(heartbeatInterval);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounting');
      }
    };
  }, [connect, ping]);

  return {
    // Estado
    isConnected,
    isValidating,
    error,
    stats,
    
    // Funciones principales
    checkCompatibility,
    getSuggestions,
    batchValidate,
    
    // Utilidades
    getStats,
    clearCache,
    ping,
    reconnect: connect
  };
}

export default useTimelineValidation;
