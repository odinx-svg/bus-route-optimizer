import { useTimeline } from '../hooks/useTimeline';
import { Bus } from 'lucide-react';

// Colores consistentes con el proyecto
const COLORS = {
  entry: {
    bg: 'bg-indigo-500',
    hover: 'hover:bg-indigo-400',
    bgOpacity: 'bg-indigo-500/20',
    text: 'text-indigo-400'
  },
  exit: {
    bg: 'bg-amber-500',
    hover: 'hover:bg-amber-400',
    bgOpacity: 'bg-amber-500/20',
    text: 'text-amber-400'
  }
};

export function Timeline({ schedule, hourRange = [6, 22], selectedBusId, onBusSelect }) {
  const { busesWithPositions, hourMarks } = useTimeline(schedule, hourRange);

  if (!schedule || schedule.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-zinc-500">
        <p className="text-sm">No hay datos de horario para mostrar</p>
      </div>
    );
  }

  return (
    <div className="w-full overflow-x-auto">
      <div className="min-w-[800px] bg-[#1c1c1f] rounded-[16px] border border-white/[0.06] overflow-hidden">
        {/* Header con horas */}
        <div className="relative h-12 border-b border-white/[0.06] bg-white/[0.02]">
          {hourMarks.map(({ hour, left }) => (
            <div
              key={hour}
              className="absolute top-0 h-full flex flex-col items-center"
              style={{ left: `${left}%` }}
            >
              <div className="h-2 w-px bg-zinc-600" />
              <span className="text-[11px] text-zinc-400 mt-1.5 font-medium tabular-nums">
                {hour}:00
              </span>
            </div>
          ))}
        </div>

        {/* Filas de buses */}
        <div className="divide-y divide-white/[0.04]">
          {busesWithPositions.map((bus) => (
            <div 
              key={bus.bus_id} 
              className={`
                relative h-16 transition-colors cursor-pointer
                ${selectedBusId === bus.bus_id ? 'bg-white/[0.06]' : 'hover:bg-white/[0.03]'}
              `}
              onClick={() => onBusSelect && onBusSelect(bus.bus_id)}
            >
              {/* Label del bus */}
              <div className="absolute left-0 top-0 h-full w-24 flex items-center px-3 border-r border-white/[0.06] bg-[#1c1c1f] z-10">
                <Bus className="w-4 h-4 text-zinc-500 mr-2 flex-shrink-0" />
                <span className="text-[12px] font-medium text-zinc-300 truncate">{bus.bus_id}</span>
              </div>

              {/* Área de rutas */}
              <div className="ml-24 h-full relative">
                {/* Líneas de hora */}
                {hourMarks.map(({ left }) => (
                  <div
                    key={left}
                    className="absolute top-0 h-full w-px bg-white/[0.04]"
                    style={{ left: `${left}%` }}
                  />
                ))}

                {/* Bloques de rutas */}
                {bus.items.map((item, index) => (
                  <RouteBlock 
                    key={`${item.route_id}-${index}`} 
                    item={item} 
                    index={index}
                    isSelected={selectedBusId === bus.bus_id}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Leyenda */}
        <div className="p-3 border-t border-white/[0.06] bg-white/[0.02] flex gap-6 text-[11px]">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-indigo-500" />
            <span className="text-zinc-400">Entrada</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-amber-500" />
            <span className="text-zinc-400">Salida</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-zinc-600" />
            <span className="text-zinc-500">Tiempo muerto</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function RouteBlock({ item, index, isSelected }) {
  const isEntry = item.type === 'entry';
  const colors = isEntry ? COLORS.entry : COLORS.exit;

  return (
    <div
      className={`
        absolute top-2.5 h-11 rounded-[8px] 
        ${colors.bg} ${colors.hover}
        text-white text-[10px]
        flex flex-col justify-center px-2.5
        cursor-pointer transition-all duration-150
        hover:shadow-lg hover:shadow-black/20
        overflow-hidden border border-white/10
        ${isSelected ? 'ring-2 ring-white/20' : ''}
      `}
      style={{
        left: `${item.left}%`,
        width: `${Math.max(item.width, 1.5)}%` // Mínimo 1.5% para visibilidad
      }}
      title={`${item.route_id}: ${item.start_time} - ${item.end_time}${item.school_name ? ` | ${item.school_name}` : ''}`}
    >
      <span className="font-medium truncate leading-tight">{item.route_id}</span>
      <span className="opacity-80 truncate tabular-nums">{item.start_time}</span>
    </div>
  );
}
