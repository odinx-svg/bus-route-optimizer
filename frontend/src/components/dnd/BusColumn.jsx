import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { SortableRoute } from './SortableRoute';
import { Bus } from 'lucide-react';

const BUS_COLORS = [
  '#6366F1', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899',
  '#06B6D4', '#F97316', '#84CC16', '#14B8A6', '#EF4444',
  '#818CF8', '#22D3EE', '#A3E635', '#FB923C', '#E879F9',
];

const getBusColor = (id) => {
  const num = parseInt(id.replace(/\D/g, ''), 10) || 0;
  return BUS_COLORS[num % BUS_COLORS.length];
};

export function BusColumn({ bus, selectedRouteId, onRouteSelect }) {
  const { setNodeRef, isOver } = useDroppable({
    id: bus.bus_id,
    data: { type: 'bus', busId: bus.bus_id }
  });

  const routeIds = bus.items.map(item => `${bus.bus_id}-${item.route_id}`);
  const color = getBusColor(bus.bus_id);
  const entries = bus.items?.filter(i => i.type === 'entry') || [];
  const exits = bus.items?.filter(i => i.type === 'exit') || [];

  return (
    <div
      ref={setNodeRef}
      className={`
        flex flex-col w-[280px] min-h-[300px] rounded-[14px] border
        transition-all duration-200 overflow-hidden flex-shrink-0
        ${isOver 
          ? 'bg-indigo-500/[0.05] border-indigo-500/[0.3] ring-2 ring-indigo-500/[0.2]' 
          : 'bg-white/[0.02] border-white/[0.04]'
        }
      `}
    >
      {/* Header */}
      <div className="flex items-center gap-3 p-3 border-b border-white/[0.04] bg-white/[0.02]">
        <div
          className="w-1 h-8 rounded-full flex-shrink-0"
          style={{ backgroundColor: color }}
        />
        <Bus className="w-4 h-4 text-zinc-500" />
        <h3 className="font-medium text-[13px] text-white">{bus.bus_id}</h3>
        <div className="ml-auto flex items-center gap-1.5">
          {entries.length > 0 && (
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-indigo-500/[0.1] text-indigo-400 font-medium">
              {entries.length}E
            </span>
          )}
          {exits.length > 0 && (
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/[0.1] text-amber-400 font-medium">
              {exits.length}X
            </span>
          )}
        </div>
      </div>

      {/* Routes container */}
      <div className="flex-1 p-2 min-h-[150px]">
        <SortableContext items={routeIds} strategy={verticalListSortingStrategy}>
          <div className="space-y-1">
            {bus.items.map((item) => (
              <SortableRoute
                key={`${bus.bus_id}-${item.route_id}`}
                route={item}
                busId={bus.bus_id}
                isSelected={selectedRouteId === item.route_id}
                onClick={() => onRouteSelect(item.route_id)}
              />
            ))}
          </div>
        </SortableContext>

        {bus.items.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center h-[150px] text-zinc-600">
            <Bus className="w-8 h-8 mb-2 opacity-30" />
            <span className="text-[11px]">Arrastra rutas aquí</span>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-3 py-2 border-t border-white/[0.04] bg-white/[0.02]">
        <span className="text-[10px] text-zinc-600">
          {bus.items.length} {bus.items.length === 1 ? 'ruta' : 'rutas'}
        </span>
      </div>
    </div>
  );
}
