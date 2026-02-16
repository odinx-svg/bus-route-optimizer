import { useDraggable } from '@dnd-kit/core';

export function DraggableUnassignedRoute({ route, isSelected, onClick }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `unassigned-${route.route_id}`,
    data: { route, source: 'unassigned' }
  });
  
  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      onClick={onClick}
      className={`
        p-2 rounded border cursor-grab
        ${isSelected ? 'border-indigo-500 bg-indigo-500/20' : 'border-gray-600 bg-gray-700'}
        ${isDragging ? 'opacity-50' : ''}
        hover:border-gray-500
        transition-colors
      `}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-white">{route.route_code}</span>
        <span className="text-[10px] text-gray-400">{route.currentStartTime}</span>
      </div>
      <div className="text-[10px] text-gray-500 truncate">
        {route.origin} → {route.destination}
      </div>
    </div>
  );
}
