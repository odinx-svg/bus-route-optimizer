import { useState } from 'react';
import { Timeline } from './Timeline';
import { ZoomIn, ZoomOut, RotateCcw, Clock } from 'lucide-react';

const MIN_HOUR_RANGE = 4; // Mínimo 4 horas de rango
const MAX_HOUR_RANGE = 20; // Máximo 20 horas de rango
const DEFAULT_START = 6;
const DEFAULT_END = 22;

export function TimelineZoomable({ schedule, selectedBusId, onBusSelect }) {
  const [hourRange, setHourRange] = useState([DEFAULT_START, DEFAULT_END]);

  const handleZoomIn = () => {
    const [start, end] = hourRange;
    const currentRange = end - start;
    if (currentRange > MIN_HOUR_RANGE) {
      // Reducir el rango desde ambos lados
      setHourRange([start + 1, end - 1]);
    }
  };

  const handleZoomOut = () => {
    const [start, end] = hourRange;
    const currentRange = end - start;
    if (currentRange < MAX_HOUR_RANGE && start > 0 && end < 24) {
      // Expandir el rango desde ambos lados
      setHourRange([Math.max(0, start - 1), Math.min(24, end + 1)]);
    }
  };

  const resetZoom = () => {
    setHourRange([DEFAULT_START, DEFAULT_END]);
  };

  const canZoomIn = hourRange[1] - hourRange[0] > MIN_HOUR_RANGE;
  const canZoomOut = hourRange[1] - hourRange[0] < MAX_HOUR_RANGE && 
                     hourRange[0] > 0 && hourRange[1] < 24;

  return (
    <div className="h-full flex flex-col">
      {/* Controles de zoom */}
      <div className="flex items-center justify-between mb-4 px-1">
        <div className="flex items-center gap-1.5">
          <button
            onClick={handleZoomIn}
            disabled={!canZoomIn}
            className="
              p-2 rounded-[10px] transition-all
              bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.06]
              disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-white/[0.04]
            "
            title="Acercar"
          >
            <ZoomIn className="w-4 h-4 text-zinc-300" />
          </button>
          <button
            onClick={handleZoomOut}
            disabled={!canZoomOut}
            className="
              p-2 rounded-[10px] transition-all
              bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.06]
              disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-white/[0.04]
            "
            title="Alejar"
          >
            <ZoomOut className="w-4 h-4 text-zinc-300" />
          </button>
          <button
            onClick={resetZoom}
            className="
              px-3 py-2 text-[11px] font-medium rounded-[10px] transition-all
              bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.06]
              text-zinc-300 flex items-center gap-1.5
            "
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset
          </button>
        </div>

        <div className="flex items-center gap-2 text-[11px] text-zinc-500">
          <Clock className="w-3.5 h-3.5" />
          <span className="tabular-nums">
            {hourRange[0]}:00 - {hourRange[1]}:00
          </span>
          <span className="text-zinc-600">
            ({hourRange[1] - hourRange[0]}h)
          </span>
        </div>
      </div>

      {/* Timeline */}
      <div className="flex-1 overflow-auto">
        <Timeline 
          schedule={schedule} 
          hourRange={hourRange}
          selectedBusId={selectedBusId}
          onBusSelect={onBusSelect}
        />
      </div>
    </div>
  );
}
