/**
 * TransferZone - Zona de transferencia de rutas
 *
 * Estados:
 * - Vacia + no drag: indicador compacto
 * - Vacia + drag: dropzone destacada
 * - Con rutas: panel expandido con tarjetas arrastrables
 */

import React from 'react';
import { useDroppable, useDraggable } from '@dnd-kit/core';
import { Package, ArrowRightLeft, Trash2, Clock3 } from 'lucide-react';

function TransferRouteCard({ route }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `transfer-${route.id}`,
    data: { type: 'route', route, source: 'transfer' },
  });

  const toneByType = {
    entry: {
      rail: 'bg-cyan-400',
      badge: 'bg-cyan-500/12 text-cyan-200 border-cyan-400/35',
    },
    exit: {
      rail: 'bg-amber-400',
      badge: 'bg-amber-500/12 text-amber-200 border-amber-400/35',
    },
  };

  const tone = toneByType[route?.type] || toneByType.entry;
  const code = route?.code || route?.id || 'Ruta';
  const start = route?.startTime || route?.start_time || '--:--';
  const end = route?.endTime || route?.end_time || '--:--';
  const school = route?.schoolName || route?.school_name || route?.school || '';

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      className={`
        relative rounded-[10px] border border-[#35506a] bg-[linear-gradient(180deg,rgba(15,26,39,0.95),rgba(10,19,30,0.95))]
        cursor-grab active:cursor-grabbing shadow-[0_8px_18px_rgba(2,8,14,0.38)]
        transition-all duration-200 overflow-hidden
        ${isDragging ? 'opacity-55 scale-[1.015] border-cyan-400/60' : 'hover:border-cyan-300/45 hover:translate-y-[-1px]'}
      `}
      title={`${code} · ${start} - ${end}`}
    >
      <div className={`absolute left-0 top-0 bottom-0 w-[2px] ${tone.rail}`} />
      <div className="pl-2.5 pr-2 py-2">
        <div className="flex items-center justify-between gap-1.5">
          <div className="text-[10px] font-semibold text-[#e8f2fa] data-mono truncate">{code}</div>
          <span className={`text-[9px] px-1.5 py-0.5 rounded border font-semibold uppercase tracking-[0.06em] ${tone.badge}`}>
            {route?.type === 'exit' ? 'SAL' : 'ENT'}
          </span>
        </div>

        {school ? (
          <div className="text-[9px] text-slate-400 truncate mt-1">{school}</div>
        ) : null}

        <div className="mt-1.5 flex items-center gap-1.5 text-[9px] text-slate-300 data-mono">
          <Clock3 className="w-3 h-3 text-slate-500" />
          <span>{start} - {end}</span>
        </div>
      </div>
    </div>
  );
}

export function TransferZone({ routes = [], isDragging = false, onRouteRemove }) {
  const { isOver, setNodeRef } = useDroppable({
    id: 'transfer-zone',
    data: { type: 'transfer-zone' },
  });

  const hasRoutes = Array.isArray(routes) && routes.length > 0;

  if (hasRoutes) {
    return (
      <div ref={setNodeRef} className="h-full flex flex-col">
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-[#132437] border border-[#2f4b64] flex items-center justify-center">
              <Package className="w-3 h-3 text-cyan-300" />
            </div>
            <span className="text-[11px] font-semibold text-slate-100 uppercase tracking-[0.08em]">Transferencia</span>
            <span className="text-[9px] px-1.5 py-0.5 rounded border border-[#32526f] text-slate-300 data-mono">
              {routes.length}
            </span>
          </div>
          <button
            onClick={() => routes.forEach((route) => onRouteRemove?.(route.id))}
            className="p-1.5 rounded-md border border-transparent text-slate-500 hover:text-rose-300 hover:border-rose-400/35 hover:bg-rose-500/10 transition-colors"
            title="Vaciar zona de transferencia"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>

        <div
          className={`
            flex-1 rounded-[12px] border p-2 overflow-y-auto transition-all
            ${isOver
              ? 'border-cyan-400/65 bg-cyan-500/8 shadow-[inset_0_0_0_1px_rgba(56,189,248,0.25)]'
              : 'border-[#2f455d] bg-[#0c1622]'}
          `}
        >
          <div className="grid grid-cols-1 gap-2">
            {routes.map((route, index) => (
              <TransferRouteCard
                key={`transfer-${route.id || index}-${index}`}
                route={route}
              />
            ))}
          </div>
        </div>

        <p className="mt-2 text-[9px] text-slate-500 text-center uppercase tracking-[0.08em] data-mono">
          Arrastra a un bus destino
        </p>
      </div>
    );
  }

  if (isDragging) {
    return (
      <div ref={setNodeRef} className="h-full flex flex-col">
        <div
          className={`
            flex-1 rounded-[12px] border border-dashed flex flex-col items-center justify-center p-4 transition-all
            ${isOver
              ? 'border-cyan-400/80 bg-cyan-500/12 shadow-[inset_0_0_0_1px_rgba(34,211,238,0.22)] scale-[1.01]'
              : 'border-[#40607d] bg-[#0d1824]'}
          `}
        >
          <ArrowRightLeft
            className={`w-6 h-6 mb-2 transition-colors ${isOver ? 'text-cyan-300' : 'text-slate-500'}`}
          />
          <span
            className={`
              text-[11px] font-semibold transition-colors uppercase tracking-[0.08em]
              ${isOver ? 'text-cyan-100' : 'text-slate-400'}
            `}
          >
            {isOver ? 'Soltar en transferencia' : 'Zona de transferencia'}
          </span>
          <span className="mt-1 text-[9px] text-slate-500 data-mono">buffer temporal de rutas</span>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col items-center justify-center">
      <div className="w-10 h-10 rounded-[10px] bg-[#111d2a] border border-[#2f455d] flex items-center justify-center">
        <Package className="w-4 h-4 text-slate-500" />
      </div>
      <span className="mt-2 text-[9px] text-slate-600 uppercase tracking-[0.08em] data-mono">Transfer</span>
    </div>
  );
}

export default TransferZone;
