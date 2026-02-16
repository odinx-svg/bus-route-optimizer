/**
 * StopEditor - Componente para editar paradas de ruta
 * 
 * Permite reordenar paradas mediante drag & drop y editar
 * sus propiedades (nombre, coordenadas, tiempo desde inicio).
 * 
 * @module components/timeline-editable/StopEditor
 * @version 1.0.0
 */

import { useState, useCallback } from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragOverlay
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  GripVertical,
  MapPin,
  School,
  Trash2,
  Clock,
  Navigation
} from 'lucide-react';

/**
 * Item de parada individual sortable
 * 
 * @param {Object} props
 * @param {Object} props.stop - Datos de la parada
 * @param {number} props.index - Índice de la parada
 * @param {boolean} props.isLocked - Si la ruta está bloqueada
 * @param {Function} props.onUpdate - Callback al actualizar
 * @param {Function} props.onRemove - Callback al eliminar
 */
function SortableStopItem({ stop, index, isLocked, onUpdate, onRemove }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({
    id: stop.tempId || stop.stop_id,
    disabled: isLocked
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 50 : 'auto',
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`
        group flex items-center gap-2 p-3 rounded-lg border
        ${isDragging 
          ? 'bg-gray-800 border-indigo-500 shadow-lg opacity-90' 
          : 'bg-gray-900/50 border-gray-800 hover:border-gray-700'
        }
        ${isLocked ? '' : 'hover:bg-gray-800/50'}
        transition-all duration-150
      `}
    >
      {/* Handle de drag */}
      <div
        {...attributes}
        {...listeners}
        className={`
          flex-shrink-0 cursor-grab active:cursor-grabbing
          ${isLocked ? 'opacity-30 cursor-not-allowed' : 'text-gray-500 hover:text-gray-300'}
        `}
      >
        <GripVertical className="w-4 h-4" />
      </div>

      {/* Número de orden */}
      <div className={`
        w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0
        ${stop.is_school 
          ? 'bg-blue-500/20 text-blue-400' 
          : 'bg-gray-700 text-gray-400'
        }
      `}>
        {index + 1}
      </div>

      {/* Icono de tipo */}
      <div className="flex-shrink-0">
        {stop.is_school ? (
          <School className="w-4 h-4 text-blue-400" />
        ) : (
          <MapPin className="w-4 h-4 text-gray-500" />
        )}
      </div>

      {/* Campos editables */}
      <div className="flex-1 min-w-0 space-y-2">
        {/* Nombre */}
        <input
          type="text"
          value={stop.stop_name || ''}
          onChange={(e) => onUpdate('stop_name', e.target.value)}
          disabled={isLocked}
          placeholder="Nombre de la parada"
          className="w-full bg-transparent border-0 border-b border-gray-700 focus:border-indigo-500 focus:outline-none text-white text-sm py-0.5 disabled:opacity-50 disabled:cursor-not-allowed placeholder:text-gray-600"
        />
        
        {/* Coordenadas */}
        <div className="flex items-center gap-2">
          <Navigation className="w-3 h-3 text-gray-600" />
          <input
            type="number"
            step="0.000001"
            value={stop.latitude ?? ''}
            onChange={(e) => onUpdate('latitude', parseFloat(e.target.value) || 0)}
            disabled={isLocked}
            placeholder="Lat"
            className="w-20 bg-transparent border-0 border-b border-gray-700 focus:border-indigo-500 focus:outline-none text-gray-400 text-xs py-0.5 font-mono disabled:opacity-50 disabled:cursor-not-allowed placeholder:text-gray-600"
          />
          <input
            type="number"
            step="0.000001"
            value={stop.longitude ?? ''}
            onChange={(e) => onUpdate('longitude', parseFloat(e.target.value) || 0)}
            disabled={isLocked}
            placeholder="Lon"
            className="w-20 bg-transparent border-0 border-b border-gray-700 focus:border-indigo-500 focus:outline-none text-gray-400 text-xs py-0.5 font-mono disabled:opacity-50 disabled:cursor-not-allowed placeholder:text-gray-600"
          />
        </div>
      </div>

      {/* Tiempo desde inicio */}
      <div className="flex items-center gap-1.5 flex-shrink-0">
        <Clock className="w-3.5 h-3.5 text-gray-500" />
        <input
          type="number"
          value={stop.time_from_start || 0}
          onChange={(e) => onUpdate('time_from_start', parseInt(e.target.value) || 0)}
          disabled={isLocked}
          className="w-12 bg-gray-800 border border-gray-700 rounded px-1.5 py-1 text-white text-xs text-center focus:border-indigo-500 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
        />
        <span className="text-gray-500 text-xs">min</span>
      </div>

      {/* Badge de colegio */}
      {stop.is_school && (
        <span className="flex-shrink-0 bg-blue-500/20 text-blue-400 text-[10px] px-2 py-0.5 rounded-full">
          Colegio
        </span>
      )}

      {/* Botón eliminar (solo si no está bloqueado y no es el colegio) */}
      {!isLocked && !stop.is_school && (
        <button
          onClick={() => onRemove()}
          className="opacity-0 group-hover:opacity-100 p-1.5 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded transition-all"
          title="Eliminar parada"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}

/**
 * Vista previa durante el drag
 */
function DragPreview({ stop, index }) {
  return (
    <div className="flex items-center gap-2 p-3 rounded-lg border bg-gray-800 border-indigo-500 shadow-xl opacity-90 rotate-2 scale-105">
      <GripVertical className="w-4 h-4 text-gray-400" />
      <div className={`
        w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold
        ${stop.is_school ? 'bg-blue-500/20 text-blue-400' : 'bg-gray-700 text-gray-400'}
      `}>
        {index + 1}
      </div>
      {stop.is_school ? (
        <School className="w-4 h-4 text-blue-400" />
      ) : (
        <MapPin className="w-4 h-4 text-gray-500" />
      )}
      <span className="text-white text-sm font-medium truncate max-w-[150px]">
        {stop.stop_name}
      </span>
    </div>
  );
}

/**
 * Componente principal de edición de paradas
 * 
 * @param {Object} props
 * @param {Array} props.stops - Lista de paradas
 * @param {boolean} props.isLocked - Si la ruta está bloqueada
 * @param {Function} props.onReorder - Callback al reordenar
 * @param {Function} props.onUpdate - Callback al actualizar una parada
 * @param {Function} props.onRemove - Callback al eliminar una parada
 */
export function StopEditor({ stops, isLocked, onReorder, onUpdate, onRemove }) {
  const [activeId, setActiveId] = useState(null);
  const [activeIndex, setActiveIndex] = useState(null);

  // Configurar sensores para drag & drop
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 }
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates
    })
  );

  const handleDragStart = useCallback((event) => {
    const { active } = event;
    setActiveId(active.id);
    const index = stops.findIndex(s => (s.tempId || s.stop_id) === active.id);
    setActiveIndex(index);
  }, [stops]);

  const handleDragEnd = useCallback((event) => {
    const { active, over } = event;

    setActiveId(null);
    setActiveIndex(null);

    if (over && active.id !== over.id) {
      const oldIndex = stops.findIndex(s => (s.tempId || s.stop_id) === active.id);
      const newIndex = stops.findIndex(s => (s.tempId || s.stop_id) === over.id);
      
      const reorderedStops = arrayMove(stops, oldIndex, newIndex);
      
      // Actualizar orden
      const updatedStops = reorderedStops.map((stop, idx) => ({
        ...stop,
        stop_order: idx + 1
      }));
      
      onReorder(updatedStops);
    }
  }, [stops, onReorder]);

  const handleUpdate = useCallback((stopId, field, value) => {
    onUpdate(stopId, { [field]: value });
  }, [onUpdate]);

  const handleRemove = useCallback((stopId) => {
    onRemove(stopId);
  }, [onRemove]);

  // Parada activa para el overlay
  const activeStop = activeId ? stops.find(s => (s.tempId || s.stop_id) === activeId) : null;

  if (!stops || stops.length === 0) {
    return (
      <div className="text-center py-8 bg-gray-900/30 rounded-lg border border-dashed border-gray-800">
        <MapPin className="w-8 h-8 mx-auto mb-2 text-gray-600" />
        <p className="text-gray-500 text-sm">No hay paradas definidas</p>
        {!isLocked && (
          <p className="text-gray-600 text-xs mt-1">Añade paradas para definir la ruta</p>
        )}
      </div>
    );
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <SortableContext
        items={stops.map(s => s.tempId || s.stop_id)}
        strategy={verticalListSortingStrategy}
      >
        <div className="space-y-2">
          {stops.map((stop, index) => (
            <SortableStopItem
              key={stop.tempId || stop.stop_id}
              stop={stop}
              index={index}
              isLocked={isLocked}
              onUpdate={(field, value) => handleUpdate(stop.tempId || stop.stop_id, field, value)}
              onRemove={() => handleRemove(stop.tempId || stop.stop_id)}
            />
          ))}
        </div>
      </SortableContext>

      <DragOverlay dropAnimation={null}>
        {activeStop ? (
          <DragPreview stop={activeStop} index={activeIndex} />
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}

/**
 * Versión simplificada para visualización solamente
 * Útil para mostrar paradas sin edición
 * 
 * @param {Object} props
 * @param {Array} props.stops - Lista de paradas
 * @param {boolean} props.compact - Modo compacto
 */
export function StopList({ stops, compact = false }) {
  if (!stops || stops.length === 0) {
    return (
      <div className="text-center py-4 text-gray-500 text-sm">
        Sin paradas
      </div>
    );
  }

  if (compact) {
    return (
      <div className="flex items-center gap-1 text-xs text-gray-400">
        <MapPin className="w-3 h-3" />
        <span>{stops.length} paradas</span>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      {stops.map((stop, index) => (
        <div
          key={stop.stop_id || index}
          className="flex items-center gap-2 py-1.5 px-2 rounded bg-gray-900/30"
        >
          <span className={`
            w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0
            ${stop.is_school ? 'bg-blue-500/20 text-blue-400' : 'bg-gray-700 text-gray-400'}
          `}>
            {index + 1}
          </span>
          {stop.is_school ? (
            <School className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
          ) : (
            <MapPin className="w-3.5 h-3.5 text-gray-500 flex-shrink-0" />
          )}
          <span className="text-gray-300 text-sm truncate flex-1">{stop.stop_name}</span>
          {stop.time_from_start > 0 && (
            <span className="text-gray-500 text-xs">+{stop.time_from_start}min</span>
          )}
        </div>
      ))}
    </div>
  );
}

export default StopEditor;
