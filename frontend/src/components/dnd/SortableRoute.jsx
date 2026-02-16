import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, ArrowUpRight, ArrowDownRight, MapPin } from 'lucide-react';

export function SortableRoute({ route, busId, isSelected, onClick }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({
    id: `${busId}-${route.route_id}`,
    data: {
      type: 'route',
      routeId: route.route_id,
      busId: busId
    }
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1
  };

  const isEntry = route.type === 'entry';
  const shifted = route.time_shift_minutes > 0;

  return (
    <div
      ref={setNodeRef}
      style={style}
      onClick={onClick}
      className={`
        group flex items-center gap-2 p-2.5 mb-2 rounded-[10px] border cursor-pointer
        transition-all duration-150 select-none
        ${isSelected
          ? 'bg-indigo-500/[0.1] border-indigo-500/[0.2]'
          : 'bg-white/[0.02] border-transparent hover:bg-white/[0.04] hover:border-white/[0.06]'
        }
        ${isDragging ? 'ring-2 ring-indigo-500 shadow-lg' : ''}
      `}
    >
      {/* Drag handle */}
      <button
        {...attributes}
        {...listeners}
        onClick={(e) => e.stopPropagation()}
        className="p-1 hover:bg-white/[0.08] rounded cursor-grab active:cursor-grabbing transition-colors"
        title="Arrastrar para mover"
      >
        <GripVertical className="w-3.5 h-3.5 text-zinc-500" />
      </button>
      
      {/* Route icon */}
      <div className={`w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 ${
        isEntry ? 'bg-indigo-500/[0.1] text-indigo-400' : 'bg-amber-500/[0.1] text-amber-400'
      }`}>
        {isEntry ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
      </div>
      
      {/* Route info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-medium text-zinc-300 truncate">
            {route.route_id}
          </span>
          <span className="text-[10px] text-zinc-600 tabular-nums flex-shrink-0 ml-2">
            {route.start_time} - {route.end_time}
          </span>
        </div>
        <div className="flex items-center gap-1 mt-0.5">
          <MapPin size={8} className="text-zinc-600 flex-shrink-0" />
          <span className="text-[10px] text-zinc-500 truncate">
            {route.school_name || 'Colegio'}
          </span>
          {shifted && (
            <span className="text-[9px] text-indigo-400 ml-auto flex-shrink-0">
              -{route.time_shift_minutes}m
            </span>
          )}
        </div>
      </div>
      
      {/* Type badge */}
      <span className={`
        text-[9px] px-1.5 py-0.5 rounded font-medium flex-shrink-0
        ${isEntry ? 'bg-indigo-500/[0.1] text-indigo-400' : 'bg-amber-500/[0.1] text-amber-400'}
      `}>
        {isEntry ? 'E' : 'X'}
      </span>
    </div>
  );
}
