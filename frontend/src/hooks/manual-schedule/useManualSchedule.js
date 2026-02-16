/**
 * Hook principal para el Editor Manual de Horarios
 * 
 * Proporciona acceso simplificado al store y utilidades comunes.
 * 
 * @module hooks/manual-schedule/useManualSchedule
 * @version 1.0.0
 */

import { useCallback, useMemo } from 'react';
import { useManualScheduleStore } from '../../stores/manualScheduleStore';

/**
 * Hook principal para operaciones CRUD del horario manual
 * @returns {Object} Operaciones y estado del horario
 */
export function useManualSchedule() {
  // Seleccionar estado del store
  const buses = useManualScheduleStore(state => state.buses);
  const availableRoutes = useManualScheduleStore(state => state.availableRoutes);
  const assignedRouteIds = useManualScheduleStore(state => state.assignedRouteIds);
  const validationStatus = useManualScheduleStore(state => state.validationStatus);
  const invalidPairs = useManualScheduleStore(state => state.invalidPairs);
  const isLoading = useManualScheduleStore(state => state.isLoading);
  const error = useManualScheduleStore(state => state.error);
  
  // Acciones
  const addBus = useManualScheduleStore(state => state.addBus);
  const removeBus = useManualScheduleStore(state => state.removeBus);
  const updateBusName = useManualScheduleStore(state => state.updateBusName);
  const assignRoute = useManualScheduleStore(state => state.assignRoute);
  const unassignRoute = useManualScheduleStore(state => state.unassignRoute);
  const moveRoute = useManualScheduleStore(state => state.moveRoute);
  const reorderRoutesInBus = useManualScheduleStore(state => state.reorderRoutesInBus);
  const setAvailableRoutes = useManualScheduleStore(state => state.setAvailableRoutes);
  const validateSchedule = useManualScheduleStore(state => state.validateSchedule);
  const reset = useManualScheduleStore(state => state.reset);
  const exportSchedule = useManualScheduleStore(state => state.exportSchedule);
  const importSchedule = useManualScheduleStore(state => state.importSchedule);
  
  // Utilidades memoizadas
  const stats = useMemo(() => ({
    totalBuses: buses.length,
    totalRoutes: availableRoutes.length,
    assignedRoutes: assignedRouteIds.size,
    unassignedRoutes: availableRoutes.length - assignedRouteIds.size,
    progress: availableRoutes.length > 0 
      ? (assignedRouteIds.size / availableRoutes.length) * 100 
      : 0,
    hasConflicts: invalidPairs.length > 0,
    isValid: validationStatus === 'valid',
  }), [buses.length, availableRoutes.length, assignedRouteIds.size, invalidPairs.length, validationStatus]);
  
  const isComplete = useMemo(() => 
    stats.unassignedRoutes === 0 && stats.isValid && !stats.hasConflicts,
    [stats]
  );
  
  return {
    // Estado
    buses,
    availableRoutes,
    assignedRouteIds,
    validationStatus,
    invalidPairs,
    isLoading,
    error,
    
    // Stats
    stats,
    isComplete,
    
    // Acciones CRUD
    addBus,
    removeBus,
    updateBusName,
    assignRoute,
    unassignRoute,
    moveRoute,
    reorderRoutesInBus,
    setAvailableRoutes,
    
    // Validación
    validateSchedule,
    
    // Utilidades
    reset,
    exportSchedule,
    importSchedule,
  };
}

export default useManualSchedule;
