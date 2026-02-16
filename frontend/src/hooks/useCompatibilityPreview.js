import { useState, useCallback, useRef } from 'react';

/**
 * Hook para obtener preview de compatibilidad entre rutas en tiempo real
 * Proporciona feedback visual inmediato mientras se arrastra
 */
export function useCompatibilityPreview() {
  const [preview, setPreview] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const abortControllerRef = useRef(null);

  /**
   * Calcula la diferencia de tiempo en minutos entre dos horas
   */
  const timeDiff = useCallback((timeA, timeB) => {
    const [hourA, minA] = timeA.split(':').map(Number);
    const [hourB, minB] = timeB.split(':').map(Number);
    
    const minutesA = hourA * 60 + minA;
    const minutesB = hourB * 60 + minB;
    
    return minutesB - minutesA;
  }, []);

  /**
   * Verifica compatibilidad entre dos rutas con el backend
   * Usa AbortController para cancelar requests pendientes
   */
  const checkCompatibility = useCallback(async (routeA, routeB) => {
    // Cancelar request anterior si existe
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    
    abortControllerRef.current = new AbortController();
    setIsLoading(true);

    try {
      const response = await fetch('/api/validate-route-compatibility', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          route_a_end: routeA.endCoordinates,
          route_b_start: routeB.startCoordinates,
          time_available_minutes: timeDiff(routeA.endTime, routeB.startTime)
        }),
        signal: abortControllerRef.current.signal
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      setPreview(result);
      return result;
    } catch (error) {
      if (error.name === 'AbortError') {
        // Request fue cancelado, no es un error real
        return null;
      }
      
      console.error('Error checking compatibility:', error);
      
      // Fallback: calcular compatibilidad localmente
      const fallbackResult = calculateFallbackCompatibility(routeA, routeB, timeDiff);
      setPreview(fallbackResult);
      return fallbackResult;
    } finally {
      setIsLoading(false);
    }
  }, [timeDiff]);

  /**
   * Limpia el estado del preview
   */
  const clearPreview = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setPreview(null);
    setIsLoading(false);
  }, []);

  /**
   * Calcula compatibilidad de fallback localmente
   * Se usa cuando el backend no responde
   */
  function calculateFallbackCompatibility(routeA, routeB, timeDiffFn) {
    const bufferMinutes = timeDiffFn(routeA.endTime, routeB.startTime);
    
    // Estimación aproximada de tiempo de viaje (assumes 30 km/h average)
    const distanceKm = estimateDistance(
      routeA.endCoordinates,
      routeB.startCoordinates
    );
    const travelTime = (distanceKm / 30) * 60; // minutos
    
    const compatible = bufferMinutes >= travelTime;
    
    return {
      compatible,
      buffer_minutes: bufferMinutes - travelTime,
      travel_time: travelTime,
      fallback: true
    };
  }

  /**
   * Estima distancia entre dos coordenadas usando Haversine
   */
  function estimateDistance(coordA, coordB) {
    if (!coordA || !coordB) return 0;
    
    const R = 6371; // Radio de la Tierra en km
    const lat1 = coordA[1] * Math.PI / 180;
    const lat2 = coordB[1] * Math.PI / 180;
    const deltaLat = (coordB[1] - coordA[1]) * Math.PI / 180;
    const deltaLon = (coordB[0] - coordA[0]) * Math.PI / 180;

    const a = Math.sin(deltaLat/2) * Math.sin(deltaLat/2) +
              Math.cos(lat1) * Math.cos(lat2) *
              Math.sin(deltaLon/2) * Math.sin(deltaLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

    return R * c;
  }

  return { 
    preview, 
    isLoading,
    checkCompatibility, 
    clearPreview 
  };
}

export default useCompatibilityPreview;
