/**
 * Hook para lógica de Drag & Drop del Editor Manual
 * 
 * Integra @dnd-kit con el store de horarios manual.
 * 
 * @module hooks/manual-schedule/useDragAndDrop
 * @version 1.0.0
 */

import { useCallback, useState } from 'react';
import { useManualScheduleStore } from '../../stores/manualScheduleStore';

/**
 * Hook para gestionar operaciones de Drag & Drop
 * @returns {Object} Handlers y estado de DnD
 */
export function useDragAndDrop() {
  const [activeDragItem, setActiveDragItem] = useState(null);
  const [dragOverBusId, setDragOverBusId] = useState(null);
  const [insertPosition, setInsertPosition] = useState(null);
  
  // Store actions
  const assignRoute = useManualScheduleStore(state => state.assignRoute);
  const unassignRoute = useManualScheduleStore(state => state.unassignRoute);
  const moveRoute = useManualScheduleStore(state => state.moveRoute);
  const reorderRoutesInBus = useManualScheduleStore(state => state.reorderRoutesInBus);
  const getRouteById = useManualScheduleStore(state => state.getRouteById);
  const getAssignmentById = useManualScheduleStore(state => state.getAssignmentById);
  
  /**
   * Handler para inicio de drag
   * @param {Object} event - Evento de dnd-kit
   */
  const handleDragStart = useCallback((event) => {
    const { active } = event;
    const data = active.data.current;
    
    setActiveDragItem({
      id: active.id,
      type: data?.type,
      ...data,
    });
  }, []);
  
  /**
   * Handler para drag sobre un contenedor
   * @param {Object} event - Evento de dnd-kit
   */
  const handleDragOver = useCallback((event) => {
    const { active, over } = event;
    
    if (!over) {
      setDragOverBusId(null);
      setInsertPosition(null);
      return;
    }
    
    const overData = over.data.current;
    
    if (overData?.type === 'bus') {
      setDragOverBusId(overData.busId);
      setInsertPosition(null);
    } else if (overData?.type === 'assigned-route') {
      setDragOverBusId(overData.busId);
      setInsertPosition(overData.position);
    } else if (overData?.type === 'drop-zone') {
      setDragOverBusId(overData.busId);
      setInsertPosition(overData.position);
    }
  }, []);
  
  /**
   * Handler para finalización de drag
   * @param {Object} event - Evento de dnd-kit
   */
  const handleDragEnd = useCallback((event) => {
    const { active, over } = event;
    
    setActiveDragItem(null);
    setDragOverBusId(null);
    setInsertPosition(null);
    
    if (!over) return;
    
    const activeData = active.data.current;
    const overData = over.data.current;
    
    if (!activeData || !overData) return;
    
    // Caso 1: Arrastrar ruta desde palette a un bus
    if (activeData.type === 'route' && overData.type === 'bus') {
      assignRoute(overData.busId, activeData.routeId);
      return;
    }
    
    // Caso 2: Arrastrar ruta desde palette a una posición específica
    if (activeData.type === 'route' && overData.type === 'drop-zone') {
      assignRoute(overData.busId, activeData.routeId, overData.position);
      return;
    }
    
    // Caso 3: Mover ruta asignada entre buses
    if (activeData.type === 'assigned-route' && overData.type === 'bus') {
      if (activeData.busId !== overData.busId) {
        moveRoute(activeData.busId, overData.busId, activeData.assignmentId);
      }
      return;
    }
    
    // Caso 4: Mover ruta asignada a posición específica
    if (activeData.type === 'assigned-route' && overData.type === 'drop-zone') {
      if (activeData.busId !== overData.busId) {
        moveRoute(activeData.busId, overData.busId, activeData.assignmentId, overData.position);
      } else {
        // Reordenar dentro del mismo bus
        const targetBus = useManualScheduleStore.getState().getBusById(activeData.busId);
        if (targetBus) {
          const currentIndex = targetBus.assignedRoutes.findIndex(
            a => a.assignmentId === activeData.assignmentId
          );
          if (currentIndex !== -1 && currentIndex !== overData.position) {
            const newOrder = [...targetBus.assignedRoutes.map(a => a.assignmentId)];
            const [moved] = newOrder.splice(currentIndex, 1);
            newOrder.splice(overData.position, 0, moved);
            reorderRoutesInBus(activeData.busId, newOrder);
          }
        }
      }
      return;
    }
    
    // Caso 5: Reordenar rutas en el mismo bus
    if (activeData.type === 'assigned-route' && overData.type === 'assigned-route') {
      if (activeData.busId === overData.busId && activeData.assignmentId !== overData.assignmentId) {
        const targetBus = useManualScheduleStore.getState().getBusById(activeData.busId);
        if (targetBus) {
          const newOrder = [...targetBus.assignedRoutes.map(a => a.assignmentId)];
          const currentIndex = newOrder.indexOf(activeData.assignmentId);
          const targetIndex = newOrder.indexOf(overData.assignmentId);
          
          if (currentIndex !== -1 && targetIndex !== -1) {
            const [moved] = newOrder.splice(currentIndex, 1);
            newOrder.splice(targetIndex, 0, moved);
            reorderRoutesInBus(activeData.busId, newOrder);
          }
        }
      }
      return;
    }
  }, [assignRoute, moveRoute, reorderRoutesInBus]);
  
  /**
   * Verifica si un drop sería válido
   * @param {Object} dragData - Datos del item arrastrado
   * @param {string} targetBusId - ID del bus objetivo
   * @returns {boolean}
   */
  const isValidDropTarget = useCallback((dragData, targetBusId) => {
    if (!dragData) return false;
    
    // Siempre permitir mover dentro del mismo bus
    if (dragData.busId === targetBusId) return true;
    
    // Para rutas nuevas, verificar que no esté ya asignada
    if (dragData.type === 'route') {
      const state = useManualScheduleStore.getState();
      return !state.assignedRouteIds.has(dragData.routeId);
    }
    
    return true;
  }, []);
  
  /**
   * Obtiene información del item siendo arrastrado
   * @returns {Object|null}
   */
  const getDragPreview = useCallback(() => {
    if (!activeDragItem) return null;
    
    const state = useManualScheduleStore.getState();
    
    if (activeDragItem.type === 'route') {
      const route = state.getRouteById(activeDragItem.routeId);
      return { type: 'route', data: route };
    }
    
    if (activeDragItem.type === 'assigned-route') {
      const result = state.getAssignmentById(activeDragItem.assignmentId);
      return { 
        type: 'assigned-route', 
        data: result?.assignment,
        route: result ? state.getRouteById(result.assignment.routeId) : null,
      };
    }
    
    return null;
  }, [activeDragItem]);
  
  return {
    // Estado
    activeDragItem,
    dragOverBusId,
    insertPosition,
    
    // Handlers
    handleDragStart,
    handleDragOver,
    handleDragEnd,
    
    // Utilidades
    isValidDropTarget,
    getDragPreview,
    
    // Reset
    resetDragState: () => {
      setActiveDragItem(null);
      setDragOverBusId(null);
      setInsertPosition(null);
    },
  };
}

export default useDragAndDrop;
