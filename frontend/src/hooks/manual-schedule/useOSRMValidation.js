/**
 * Hook para validación con OSRM en tiempo real
 * 
 * Gestiona el cálculo de tiempos de transición entre rutas
 * usando el cache y llamadas al backend cuando es necesario.
 * 
 * @module hooks/manual-schedule/useOSRMValidation
 * @version 1.0.0
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useManualScheduleStore } from '../../stores/manualScheduleStore';

// Configuración
const OSRM_BATCH_SIZE = 5;
const OSRM_DEBOUNCE_MS = 300;

/**
 * Hook para gestionar validación OSRM
 * @returns {Object} Funciones y estado de validación OSRM
 */
export function useOSRMValidation() {
  const [isCalculating, setIsCalculating] = useState(false);
  const [pendingCalculations, setPendingCalculations] = useState(0);
  const calculationQueue = useRef([]);
  const debounceTimer = useRef(null);
  
  // Store selectors
  const osrmCache = useManualScheduleStore(state => state.osrmCache);
  const setOSRMTime = useManualScheduleStore(state => state.setOSRMTime);
  const getOSRMTime = useManualScheduleStore(state => state.getOSRMTime);
  const buses = useManualScheduleStore(state => state.buses);
  const availableRoutes = useManualScheduleStore(state => state.availableRoutes);
  
  /**
   * Calcula el tiempo OSRM entre dos rutas
   * @param {string} routeAId - ID ruta origen
   * @param {string} routeBId - ID ruta destino
   * @returns {Promise<Object>} Resultado del cálculo
   */
  const calculateTransitionTime = useCallback(async (routeAId, routeBId) => {
    // Verificar cache primero
    const cached = getOSRMTime(routeAId, routeBId);
    if (cached) {
      return cached;
    }
    
    const routeA = availableRoutes.find(r => r.route_id === routeAId);
    const routeB = availableRoutes.find(r => r.route_id === routeBId);
    
    if (!routeA || !routeB) {
      throw new Error('Ruta no encontrada');
    }
    
    try {
      const response = await fetch('/api/osrm/time', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          fromLat: routeA.end_coords[0],
          fromLng: routeA.end_coords[1],
          toLat: routeB.start_coords[0],
          toLng: routeB.start_coords[1],
          routeAId,
          routeBId,
        }),
      });
      
      if (!response.ok) {
        throw new Error('Error calculando tiempo OSRM');
      }
      
      const data = await response.json();
      
      // Guardar en cache
      const cacheEntry = {
        durationMinutes: data.durationMinutes,
        distanceMeters: data.distanceMeters,
        computedAt: Date.now(),
        geometry: data.geometry,
      };
      
      setOSRMTime(routeAId, routeBId, cacheEntry);
      
      return cacheEntry;
    } catch (error) {
      console.error('Error OSRM:', error);
      // Retornar valor por defecto en caso de error
      return {
        durationMinutes: 15, // Valor por defecto conservador
        distanceMeters: 0,
        computedAt: Date.now(),
        isDefault: true,
      };
    }
  }, [availableRoutes, getOSRMTime, setOSRMTime]);
  
  /**
   * Calcula todos los tiempos necesarios para el horario actual
   */
  const calculateAllMissingTransitions = useCallback(async () => {
    const missing = [];
    
    // Encontrar todas las transiciones que necesitan cálculo
    buses.forEach(bus => {
      for (let i = 1; i < bus.assignedRoutes.length; i++) {
        const prev = bus.assignedRoutes[i - 1];
        const curr = bus.assignedRoutes[i];
        const cacheKey = `${prev.routeId}_end_${curr.routeId}_start`;
        
        if (!osrmCache.has(cacheKey)) {
          missing.push({ routeAId: prev.routeId, routeBId: curr.routeId });
        }
      }
    });
    
    if (missing.length === 0) return;
    
    setPendingCalculations(missing.length);
    setIsCalculating(true);
    
    // Procesar en batches
    for (let i = 0; i < missing.length; i += OSRM_BATCH_SIZE) {
      const batch = missing.slice(i, i + OSRM_BATCH_SIZE);
      
      await Promise.all(
        batch.map(({ routeAId, routeBId }) => 
          calculateTransitionTime(routeAId, routeBId)
        )
      );
      
      setPendingCalculations(prev => Math.max(0, prev - batch.length));
    }
    
    setIsCalculating(false);
  }, [buses, osrmCache, calculateTransitionTime]);
  
  /**
   * Pre-calcula tiempos para rutas candidatas
   * @param {string} routeAId - Ruta origen
   * @param {string[]} candidateRouteIds - Rutas candidatas
   */
  const precalculateForCandidates = useCallback(async (routeAId, candidateRouteIds) => {
    const uncached = candidateRouteIds.filter(routeBId => {
      const cacheKey = `${routeAId}_end_${routeBId}_start`;
      return !osrmCache.has(cacheKey);
    });
    
    if (uncached.length === 0) return;
    
    // Agregar a cola
    calculationQueue.current.push(
      ...uncached.map(routeBId => ({ routeAId, routeBId }))
    );
    
    // Debounce para procesar
    clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(async () => {
      const toProcess = calculationQueue.current.splice(0);
      
      for (const { routeAId, routeBId } of toProcess) {
        await calculateTransitionTime(routeAId, routeBId);
      }
    }, OSRM_DEBOUNCE_MS);
  }, [osrmCache, calculateTransitionTime]);
  
  /**
   * Verifica si dos rutas tienen tiempo de transición calculado
   * @param {string} routeAId - Ruta origen
   * @param {string} routeBId - Ruta destino
   * @returns {boolean}
   */
  const hasTransitionTime = useCallback((routeAId, routeBId) => {
    return !!getOSRMTime(routeAId, routeBId);
  }, [getOSRMTime]);
  
  /**
   * Obtiene el tiempo de transición (cacheado o por defecto)
   * @param {string} routeAId - Ruta origen
   * @param {string} routeBId - Ruta destino
   * @returns {number} Minutos de transición
   */
  const getTransitionTime = useCallback((routeAId, routeBId) => {
    const cached = getOSRMTime(routeAId, routeBId);
    return cached?.durationMinutes || 15; // Default 15 min
  }, [getOSRMTime]);
  
  // Calcular transiciones faltantes al cambiar los buses
  useEffect(() => {
    calculateAllMissingTransitions();
  }, [buses, calculateAllMissingTransitions]);
  
  return {
    isCalculating,
    pendingCalculations,
    calculateTransitionTime,
    calculateAllMissingTransitions,
    precalculateForCandidates,
    hasTransitionTime,
    getTransitionTime,
  };
}

export default useOSRMValidation;
