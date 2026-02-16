/**
 * useScheduleValidation - Hook para validación de horarios en tiempo real via WebSocket
 * 
 * Conecta al endpoint /ws/validate-schedule para obtener validación OSRM
 * instantánea mientras el usuario edita el horario.
 */

import { useEffect, useRef, useState, useCallback } from 'react';

const resolveWsBaseUrls = () => {
  const candidates = [];

  const pushCandidate = (url) => {
    if (!url || typeof url !== 'string') return;
    const normalized = url.replace(/\/$/, '');
    if (!candidates.includes(normalized)) {
      candidates.push(normalized);
    }
  };

  if (import.meta.env.VITE_WS_URL) {
    pushCandidate(import.meta.env.VITE_WS_URL);
  }

  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host = window.location.hostname;
    if (host === 'localhost') {
      // Priorizar IPv4 local: evita fallos en Windows cuando localhost resuelve a ::1.
      pushCandidate(`${protocol}://127.0.0.1:8000`);
    }
    pushCandidate(`${protocol}://${host}:8000`);
  }

  pushCandidate('ws://127.0.0.1:8000');
  pushCandidate('ws://localhost:8000');
  return candidates;
};

const wsToHttp = (wsUrl) => wsUrl.replace(/^wss?:\/\//i, (prefix) => (
  prefix.toLowerCase().startsWith('wss') ? 'https://' : 'http://'
));

const checkBackendHealth = async (wsBaseUrl) => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(`${wsToHttp(wsBaseUrl)}/health`, {
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

export function useScheduleValidation() {
  const wsRef = useRef(null);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionState, setConnectionState] = useState('connecting'); // connecting | connected | reconnecting | disconnected
  const [validating, setValidating] = useState(false);
  const [lastValidation, setLastValidation] = useState(null);
  const pendingRequestRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const heartbeatIntervalRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const wsBaseUrlsRef = useRef([]);
  const wsBaseUrlIndexRef = useRef(0);

  const extractLocations = useCallback((route) => {
    const getLat = (point) => {
      if (!point || typeof point !== 'object') return null;
      if (Number.isFinite(point.lat)) return point.lat;
      if (Number.isFinite(point.latitude)) return point.latitude;
      return null;
    };

    const getLon = (point) => {
      if (!point || typeof point !== 'object') return null;
      if (Number.isFinite(point.lon)) return point.lon;
      if (Number.isFinite(point.lng)) return point.lng;
      if (Number.isFinite(point.longitude)) return point.longitude;
      return null;
    };

    if (Array.isArray(route?.start_location) && Array.isArray(route?.end_location)) {
      return {
        start_location: route.start_location,
        end_location: route.end_location,
      };
    }

    if (Array.isArray(route?.start_loc) && Array.isArray(route?.end_loc)) {
      return {
        start_location: route.start_loc,
        end_location: route.end_loc,
      };
    }

    if (Array.isArray(route?.rawRoute?.start_location) && Array.isArray(route?.rawRoute?.end_location)) {
      return {
        start_location: route.rawRoute.start_location,
        end_location: route.rawRoute.end_location,
      };
    }

    if (Array.isArray(route?.rawRoute?.start_loc) && Array.isArray(route?.rawRoute?.end_loc)) {
      return {
        start_location: route.rawRoute.start_loc,
        end_location: route.rawRoute.end_loc,
      };
    }

    const stops = Array.isArray(route?.stops) ? route.stops : [];
    if (stops.length > 0) {
      const first = stops[0];
      const last = stops[stops.length - 1];

      const firstLat = getLat(first);
      const firstLon = getLon(first);
      const lastLat = getLat(last);
      const lastLon = getLon(last);

      if (Number.isFinite(firstLat) && Number.isFinite(firstLon) && Number.isFinite(lastLat) && Number.isFinite(lastLon)) {
        return {
          start_location: [firstLat, firstLon],
          end_location: [lastLat, lastLon],
        };
      }
    }

    // Fallback to avoid backend parse errors
    return {
      start_location: [0, 0],
      end_location: [0, 0],
    };
  }, []);

  const serializeRoute = useCallback((route) => {
    const locations = extractLocations(route);
    return {
      id: route.id || route.route_id,
      route_id: route.route_id || route.id,
      start_time: route.startTime || route.start_time,
      end_time: route.endTime || route.end_time,
      type: route.type || 'entry',
      school_name: route.school || route.school_name || null,
      stops: route.stops || [],
      ...locations,
    };
  }, [extractLocations]);

  // Conectar WebSocket
  useEffect(() => {
    wsBaseUrlsRef.current = resolveWsBaseUrls();
    wsBaseUrlIndexRef.current = 0;
    let disposed = false;

    const scheduleReconnect = (opened) => {
      if (disposed) return;
      setConnectionState('reconnecting');
      reconnectAttemptsRef.current += 1;
      const baseDelay = opened ? 1200 : 900;
      const backoff = Math.min(baseDelay * Math.pow(1.8, reconnectAttemptsRef.current), 15000);
      const jitter = Math.floor(Math.random() * 500);
      reconnectTimeoutRef.current = setTimeout(connect, backoff + jitter);
    };

    const connect = async () => {
      if (disposed) return;
      setConnectionState('connecting');
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        return;
      }
      const wsBaseUrl = wsBaseUrlsRef.current[wsBaseUrlIndexRef.current] || 'ws://127.0.0.1:8000';
      let hasOpened = false;

      try {
        const healthy = await checkBackendHealth(wsBaseUrl);
        if (!healthy) {
          // No bloquear por health: intentar WS igualmente (el health puede tardar y dar falsos negativos).
          console.debug('[ValidationWS] Health check not ready, trying WebSocket anyway');
        }

        if (wsRef.current) {
          try {
            wsRef.current.close();
          } catch (e) {
            console.debug('[ValidationWS] Previous socket close failed', e);
          }
          wsRef.current = null;
        }

        const ws = new WebSocket(`${wsBaseUrl}/ws/validate-schedule`);
        
        ws.onopen = () => {
          hasOpened = true;
          reconnectAttemptsRef.current = 0;
          console.log('[ValidationWS] Connected');
          setIsConnected(true);
          setConnectionState('connected');

          if (heartbeatIntervalRef.current) {
            clearInterval(heartbeatIntervalRef.current);
          }
          heartbeatIntervalRef.current = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              try {
                ws.send(JSON.stringify({ type: 'ping' }));
              } catch (e) {
                console.debug('[ValidationWS] Heartbeat send failed', e);
              }
            }
          }, 20000);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'connected') {
              console.log('[ValidationWS] Session:', data.session_id);
            }
            
            if (data.type === 'validation_result') {
              const normalized = {
                feasible: !!(data.compatible ?? data.is_compatible),
                travel_time: data.travel_time ?? null,
                buffer: data.buffer_minutes ?? null,
                suggested_start_time: data.suggested_start ?? null,
                issue: data.issue ?? null,
              };
              setLastValidation(normalized);
              setValidating(false);
              
              // Resolver promise pendiente
              if (pendingRequestRef.current) {
                pendingRequestRef.current.resolve(normalized);
                pendingRequestRef.current = null;
              }
            }

            if (data.type === 'full_validation') {
              const normalized = {
                feasible: !!data.is_valid,
                issues: data.issues || [],
                message: data.is_valid
                  ? 'Horario viable'
                  : `Se encontraron ${data.issues_count || (data.issues?.length || 0)} incidencias`,
              };
              setLastValidation(normalized);
              setValidating(false);

              if (pendingRequestRef.current) {
                pendingRequestRef.current.resolve(normalized);
                pendingRequestRef.current = null;
              }
            }

            if (data.type === 'bus_validation') {
              const normalized = {
                feasible: !!data.feasible,
                issues: data.issues || [],
                issues_count: data.issues_count ?? (data.issues?.length || 0),
                message: data.message || '',
                total_travel_time: data.total_travel_time,
                efficiency_score: data.efficiency_score,
              };
              setLastValidation(normalized);
              setValidating(false);

              if (pendingRequestRef.current) {
                pendingRequestRef.current.resolve(normalized);
                pendingRequestRef.current = null;
              }
            }

            if (data.type === 'all_buses_validation') {
              const normalized = {
                generated_at: data.generated_at || new Date().toISOString(),
                summary: data.summary || {},
                days: data.days || [],
                incidents: data.incidents || [],
                validation_time_ms: data.validation_time_ms,
              };
              setLastValidation(normalized);
              setValidating(false);

              if (pendingRequestRef.current) {
                pendingRequestRef.current.resolve(normalized);
                pendingRequestRef.current = null;
              }
            }
            
            if (data.type === 'error') {
              const errorMessage = data.message || data.error || 'Validation error';
              console.error('[ValidationWS] Error:', errorMessage);
              setValidating(false);
              
              if (pendingRequestRef.current) {
                pendingRequestRef.current.reject(new Error(errorMessage));
                pendingRequestRef.current = null;
              }
            }
          } catch (e) {
            console.error('[ValidationWS] Parse error:', e);
          }
        };

        ws.onclose = () => {
          console.log('[ValidationWS] Disconnected');
          setIsConnected(false);
          setConnectionState('reconnecting');

          if (heartbeatIntervalRef.current) {
            clearInterval(heartbeatIntervalRef.current);
            heartbeatIntervalRef.current = null;
          }

          // If never opened, try next candidate base URL first.
          if (!hasOpened && wsBaseUrlsRef.current.length > 1) {
            wsBaseUrlIndexRef.current =
              (wsBaseUrlIndexRef.current + 1) % wsBaseUrlsRef.current.length;
          }

          if (!disposed) {
            scheduleReconnect(hasOpened);
          }
        };

        ws.onerror = (error) => {
          console.debug('[ValidationWS] Socket error event', error);
          setConnectionState('reconnecting');
        };

        wsRef.current = ws;
      } catch (e) {
        console.error('[ValidationWS] Connection failed:', e);
        setConnectionState('reconnecting');
        scheduleReconnect(false);
      }
    };

    connect();

    return () => {
      disposed = true;
      setConnectionState('disconnected');
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current);
        heartbeatIntervalRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  // Validar conexión entre dos rutas (para DnD)
  const validateConnection = useCallback((currentRoute, nextRoute) => {
    return new Promise((resolve, reject) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        // Fallback si no hay conexión: asumir válido
        resolve({ feasible: true, fallback: true });
        return;
      }

      setValidating(true);
      
      // Guardar referencia para resolver cuando llegue respuesta
      pendingRequestRef.current = { resolve, reject };

      wsRef.current.send(JSON.stringify({
        type: 'validate_connection',
        route_a: serializeRoute(currentRoute),
        route_b: serializeRoute(nextRoute)
      }));

      // Timeout de 5 segundos
      setTimeout(() => {
        if (pendingRequestRef.current) {
          pendingRequestRef.current.reject(new Error('Validation timeout'));
          pendingRequestRef.current = null;
          setValidating(false);
        }
      }, 5000);
    });
  }, [serializeRoute]);

  // Validar horario completo
  const validateFullSchedule = useCallback((buses) => {
    return new Promise((resolve, reject) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        resolve({ feasible: true, fallback: true });
        return;
      }

      setValidating(true);
      pendingRequestRef.current = { resolve, reject };

      wsRef.current.send(JSON.stringify({
        type: 'validate_full_schedule',
        routes: buses.flatMap(bus => 
          bus.routes.map(route => ({
            ...serializeRoute(route),
            bus_id: bus.id,
          }))
        )
      }));

      setTimeout(() => {
        if (pendingRequestRef.current) {
          pendingRequestRef.current.reject(new Error('Validation timeout'));
          pendingRequestRef.current = null;
          setValidating(false);
        }
      }, 10000);
    });
  }, [serializeRoute]);

  // Validar un bus completo (para el botón de comprobación)
  const validateBus = useCallback((bus) => {
    return new Promise((resolve, reject) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        // Fallback si no hay conexión
        resolve({ 
          feasible: true, 
          fallback: true,
          message: 'Sin conexión OSRM - no se puede validar'
        });
        return;
      }

      setValidating(true);
      pendingRequestRef.current = { resolve, reject };

      // Enviar solo las rutas de este bus
      const routes = bus.routes.map(route => ({
        ...serializeRoute(route),
        route_code: route.code,
      }));

      wsRef.current.send(JSON.stringify({
        type: 'validate_bus',
        bus_id: bus.id,
        routes: routes
      }));

      // Timeout de 15 segundos para validación completa
      setTimeout(() => {
        if (pendingRequestRef.current) {
          pendingRequestRef.current.reject(new Error('Validation timeout'));
          pendingRequestRef.current = null;
          setValidating(false);
        }
      }, 15000);
    });
  }, [serializeRoute]);

  // Validar todos los buses (por día)
  const validateAllBuses = useCallback((days, includeValidBuses = false) => {
    return new Promise((resolve, reject) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        resolve({
          generated_at: new Date().toISOString(),
          summary: {
            total_buses: 0,
            feasible_buses: 0,
            buses_with_issues: 0,
            incidents_total: 0,
            incidents_error: 0,
            incidents_warning: 0,
            incidents_info: 0,
          },
          days: [],
          incidents: [],
          fallback: true,
          message: 'Sin conexión OSRM - no se puede validar globalmente',
        });
        return;
      }

      setValidating(true);
      pendingRequestRef.current = { resolve, reject };

      wsRef.current.send(JSON.stringify({
        type: 'validate_all_buses',
        days: Array.isArray(days) ? days : [],
        include_valid_buses: !!includeValidBuses,
      }));

      setTimeout(() => {
        if (pendingRequestRef.current) {
          pendingRequestRef.current.reject(new Error('Validation timeout'));
          pendingRequestRef.current = null;
          setValidating(false);
        }
      }, 30000);
    });
  }, []);

  // Verificar si una ruta puede ser asignada a un bus
  const canAssignRoute = useCallback(async (route, busRoutes) => {
    if (busRoutes.length === 0) return { feasible: true };

    const toMinutes = (time) => {
      if (!time || typeof time !== 'string') return 0;
      const [h = 0, m = 0] = time.split(':').map(Number);
      return (h * 60) + m;
    };

    // Ordenar rutas del bus por hora
    const sortedRoutes = [...busRoutes, route].sort((a, b) => {
      return toMinutes(a.startTime || a.start_time) - toMinutes(b.startTime || b.start_time);
    });

    // Encontrar posición de la nueva ruta
    const newIndex = sortedRoutes.findIndex(r => r.id === route.id);
    
    // Validar con ruta anterior (si existe)
    if (newIndex > 0) {
      const prevRoute = sortedRoutes[newIndex - 1];
      const result = await validateConnection(prevRoute, route);
      if (!result.feasible) {
        return {
          feasible: false,
          reason: `No hay tiempo suficiente desde ${prevRoute.code}: necesita ${result.travel_time}min, solo hay ${result.buffer}min`,
          suggestion: result.suggested_start_time
        };
      }
    }

    // Validar con ruta siguiente (si existe)
    if (newIndex < sortedRoutes.length - 1) {
      const nextRoute = sortedRoutes[newIndex + 1];
      const result = await validateConnection(route, nextRoute);
      if (!result.feasible) {
        return {
          feasible: false,
          reason: `No hay tiempo suficiente para llegar a ${nextRoute.code}: necesita ${result.travel_time}min, solo hay ${result.buffer}min`,
          suggestion: result.suggested_end_time
        };
      }
    }

    return { feasible: true };
  }, [validateConnection]);

  return {
    isConnected,
    connectionState,
    validating,
    lastValidation,
    validateConnection,
    validateFullSchedule,
    validateBus,
    validateAllBuses,
    canAssignRoute
  };
}

export default useScheduleValidation;
