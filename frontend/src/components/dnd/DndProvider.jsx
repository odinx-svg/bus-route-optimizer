/**
 * DndProvider - Proveedor principal de Drag & Drop usando @dnd-kit
 * 
 * Características:
 * - Sensores configurados (Pointer, Keyboard, Touch)
 * - Detección de colisiones por esquinas cercanas
 * - DragOverlay para preview visual
 * - Callbacks: onDragStart, onDragOver, onDragEnd
 */
import React, { createContext, useContext, useState, useCallback } from 'react';
import {
  DndContext,
  closestCorners,
  PointerSensor,
  KeyboardSensor,
  TouchSensor,
  useSensor,
  useSensors,
  DragOverlay,
  defaultDropAnimationSideEffects,
} from '@dnd-kit/core';
import {
  sortableKeyboardCoordinates,
} from '@dnd-kit/sortable';

// Contexto propio del workspace DnD
const DnDWorkspaceContext = createContext(null);

export function useDnD() {
  const context = useContext(DnDWorkspaceContext);
  if (!context) {
    throw new Error('useDnD debe usarse dentro de DndProvider');
  }
  return context;
}

const dropAnimation = {
  sideEffects: defaultDropAnimationSideEffects({
    styles: {
      active: {
        opacity: '0.5',
      },
    },
  }),
};

export function DndProvider({ 
  children, 
  onDragStart,
  onDragOver,
  onDragEnd,
  dragOverlayRenderer,
}) {
  const [activeDragItem, setActiveDragItem] = useState(null);
  const [isDragging, setIsDragging] = useState(false);

  // Configuración de sensores
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { 
        distance: 8,
        delay: 0,
        tolerance: 0,
      },
    }),
    useSensor(TouchSensor, {
      activationConstraint: {
        delay: 200,
        tolerance: 5,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragStart = useCallback((event) => {
    const { active } = event;
    setActiveDragItem(active.data.current);
    setIsDragging(true);
    onDragStart?.(event);
  }, [onDragStart]);

  const handleDragOver = useCallback((event) => {
    onDragOver?.(event);
  }, [onDragOver]);

  const handleDragEnd = useCallback((event) => {
    setIsDragging(false);
    setActiveDragItem(null);
    
    // Llamar al callback de la aplicación
    onDragEnd?.(event);
  }, [onDragEnd]);

  const handleDragCancel = useCallback(() => {
    setIsDragging(false);
    setActiveDragItem(null);
  }, []);

  const contextValue = {
    activeDragItem,
    isDragging,
  };

  return (
    <DnDWorkspaceContext.Provider value={contextValue}>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
        onDragCancel={handleDragCancel}
      >
        {children}
        
        {/* DragOverlay para preview visual al arrastrar */}
        <DragOverlay dropAnimation={dropAnimation}>
          {activeDragItem && dragOverlayRenderer?.(activeDragItem)}
        </DragOverlay>
      </DndContext>
    </DnDWorkspaceContext.Provider>
  );
}

export default DndProvider;
