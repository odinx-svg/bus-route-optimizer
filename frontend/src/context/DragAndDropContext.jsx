import React, { createContext, useContext, useState } from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
} from '@dnd-kit/sortable';

const DnDContext = createContext();

export function DragAndDropProvider({ children, schedule, onScheduleChange }) {
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 }
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates
    })
  );

  const handleDragEnd = (event) => {
    const { active, over } = event;
    
    if (!over || active.id === over.id) return;

    const activeData = active.data.current;
    const overData = over.data.current;

    if (activeData?.type === 'route' && overData?.type === 'route') {
      // Mover ruta entre buses o reordenar
      const newSchedule = moveRouteBetweenBuses(
        schedule,
        activeData.routeId,
        activeData.busId,
        overData.busId,
        overData.routeId
      );
      onScheduleChange(newSchedule);
    } else if (activeData?.type === 'route' && overData?.type === 'bus') {
      // Mover ruta a un bus vacío o como último elemento
      const newSchedule = moveRouteToBus(
        schedule,
        activeData.routeId,
        activeData.busId,
        overData.busId
      );
      onScheduleChange(newSchedule);
    }
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      {children}
    </DndContext>
  );
}

function moveRouteBetweenBuses(schedule, routeId, fromBusId, toBusId, overRouteId) {
  // Deep copy para no mutar el estado original
  const newSchedule = JSON.parse(JSON.stringify(schedule));
  
  const fromBus = newSchedule.find(b => b.bus_id === fromBusId);
  const toBus = newSchedule.find(b => b.bus_id === toBusId);
  
  if (!fromBus || !toBus) return schedule;
  
  const routeIndex = fromBus.items.findIndex(i => i.route_id === routeId);
  if (routeIndex === -1) return schedule;
  
  // Extraer la ruta del bus origen
  const [route] = fromBus.items.splice(routeIndex, 1);
  
  if (fromBusId === toBusId) {
    // Reordenar dentro del mismo bus
    const overIndex = toBus.items.findIndex(i => i.route_id === overRouteId);
    if (overIndex !== -1) {
      toBus.items.splice(overIndex, 0, route);
    } else {
      toBus.items.push(route);
    }
  } else {
    // Mover a otro bus
    const overIndex = toBus.items.findIndex(i => i.route_id === overRouteId);
    if (overIndex !== -1) {
      toBus.items.splice(overIndex, 0, route);
    } else {
      toBus.items.push(route);
    }
  }
  
  // Limpiar buses vacíos (opcional - depende del comportamiento deseado)
  return newSchedule.filter(b => b.items.length > 0);
}

function moveRouteToBus(schedule, routeId, fromBusId, toBusId) {
  const newSchedule = JSON.parse(JSON.stringify(schedule));
  
  const fromBus = newSchedule.find(b => b.bus_id === fromBusId);
  const toBus = newSchedule.find(b => b.bus_id === toBusId);
  
  if (!fromBus || !toBus) return schedule;
  
  const routeIndex = fromBus.items.findIndex(i => i.route_id === routeId);
  if (routeIndex === -1) return schedule;
  
  const [route] = fromBus.items.splice(routeIndex, 1);
  toBus.items.push(route);
  
  // Limpiar buses vacíos
  return newSchedule.filter(b => b.items.length > 0);
}
