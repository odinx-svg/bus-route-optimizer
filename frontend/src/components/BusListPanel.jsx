import React, { useState, useMemo } from 'react';
import {
  ChevronRight, ChevronDown, MapPin, Download, Search,
  ArrowUpRight, ArrowDownRight, X, LayoutGrid, List
} from 'lucide-react';
import { DraggableSchedule } from './DraggableSchedule';
import { buildRouteCapacityMap, getBusMinSeats, getItemCapacityNeeded } from '../utils/capacity';

const BUS_COLORS = [
  '#6366F1', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899',
  '#06B6D4', '#F97316', '#84CC16', '#14B8A6', '#EF4444',
  '#818CF8', '#22D3EE', '#A3E635', '#FB923C', '#E879F9',
];

const getBusColor = (id) => {
  const num = parseInt(id.replace(/\D/g, ''), 10) || 0;
  return BUS_COLORS[num % BUS_COLORS.length];
};

const getBusOrderValue = (busId = '') => {
  const match = String(busId).match(/\d+/);
  if (!match) return Number.MAX_SAFE_INTEGER;
  const parsed = Number(match[0]);
  return Number.isFinite(parsed) ? parsed : Number.MAX_SAFE_INTEGER;
};

const timeToMinutes = (t) => {
  if (!t) return 0;
  const [h, m] = String(t).split(':').map(Number);
  return h * 60 + m;
};

const getRouteOrderValue = (routeId) => {
  const match = String(routeId || '').match(/\d+/);
  if (!match) return Number.MAX_SAFE_INTEGER;
  const parsed = Number(match[0]);
  return Number.isFinite(parsed) ? parsed : Number.MAX_SAFE_INTEGER;
};

const sortItemsByTimeAndNumber = (items = []) => {
  return [...(items || [])].sort((a, b) => {
    const startDiff = timeToMinutes(a?.start_time) - timeToMinutes(b?.start_time);
    if (startDiff !== 0) return startDiff;
    const routeDiff = getRouteOrderValue(a?.route_id) - getRouteOrderValue(b?.route_id);
    if (routeDiff !== 0) return routeDiff;
    return String(a?.route_id || '').localeCompare(String(b?.route_id || ''), 'es', { sensitivity: 'base', numeric: true });
  });
};

const buildConnectionSelectionId = (busId, fromRouteId, toRouteId, index) => (
  `conn:${encodeURIComponent(String(busId || ''))}:${encodeURIComponent(String(fromRouteId || ''))}:${encodeURIComponent(String(toRouteId || ''))}:${index}`
);

const getPositioningMinutes = (item) => {
  const raw = item?.positioning_minutes ?? item?.deadhead_minutes ?? item?.deadhead ?? 0;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? Math.max(0, Math.round(parsed)) : 0;
};

const buildBusConnections = (busId, orderedItems = []) => {
  const connections = [];
  for (let i = 0; i < orderedItems.length - 1; i++) {
    const current = orderedItems[i];
    const next = orderedItems[i + 1];
    const available = Math.max(0, timeToMinutes(next?.start_time) - timeToMinutes(current?.end_time));
    const required = getPositioningMinutes(next);
    const margin = available - required;
    connections.push({
      id: buildConnectionSelectionId(busId, current?.route_id, next?.route_id, i),
      fromRouteId: current?.route_id,
      toRouteId: next?.route_id,
      endTime: current?.end_time,
      startTime: next?.start_time,
      availableMinutes: available,
      requiredMinutes: required,
      marginMinutes: margin,
    });
  }
  return connections;
};

const MiniTimeline = ({ items }) => {
  if (!items || items.length === 0) return null;

  const DAY_START = 6 * 60;
  const DAY_END = 20 * 60;
  const RANGE = DAY_END - DAY_START;

  return (
    <div className="mt-2 h-[6px] bg-white/[0.04] rounded-full overflow-hidden relative">
      {items.map((item, idx) => {
        const start = timeToMinutes(item.start_time);
        const end = timeToMinutes(item.end_time);
        const left = Math.max(0, ((start - DAY_START) / RANGE) * 100);
        const width = Math.max(1.5, ((end - start) / RANGE) * 100);
        const isEntry = item.type === 'entry';

        return (
          <div
            key={idx}
            className="absolute top-0 h-full rounded-full"
            style={{
              left: `${left}%`,
              width: `${width}%`,
              backgroundColor: isEntry ? '#818CF8' : '#FBBF24',
              opacity: 0.7,
            }}
          />
        );
      })}
    </div>
  );
};

const RouteCard = ({ item, isSelected, onClick, orderNumber = null, routeCapacityMap = null }) => {
  const isEntry = item.type === 'entry';
  const shifted = item.time_shift_minutes > 0;
  const seatsNeeded = getItemCapacityNeeded(item, routeCapacityMap);

  return (
    <div
      onClick={onClick}
      className={`
        p-2.5 rounded-[10px] cursor-pointer transition-all duration-150 border
        ${isSelected
          ? 'bg-indigo-500/[0.1] border-indigo-500/[0.2]'
          : 'bg-white/[0.02] border-transparent hover:bg-white/[0.04] hover:border-white/[0.06]'
        }
      `}
    >
      <div className="flex items-center gap-2.5">
        <div className={`w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 ${
          isEntry ? 'bg-indigo-500/[0.1] text-indigo-400' : 'bg-amber-500/[0.1] text-amber-400'
        }`}>
          {isEntry ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <div className="min-w-0 flex items-center gap-1.5">
              {orderNumber !== null && (
                <span className="text-[9px] px-1.5 py-0.5 rounded-md bg-white/[0.06] text-zinc-300 tabular-nums flex-shrink-0">
                  {orderNumber}
                </span>
              )}
              <span className="text-[11px] font-medium text-zinc-300 truncate">
                {item.route_id}
              </span>
            </div>
            <span className="text-[10px] text-zinc-600 tabular-nums flex-shrink-0 ml-2">
              {item.start_time} - {item.end_time}
            </span>
          </div>
          <div className="flex items-center gap-1 mt-0.5">
            <MapPin size={8} className="text-zinc-600 flex-shrink-0" />
            <span className="text-[10px] text-zinc-500 truncate">
              {item.school_name || 'Colegio'}
            </span>
            {seatsNeeded > 0 && (
              <span className="text-[9px] px-1.5 py-0.5 rounded-md bg-cyan-500/[0.1] text-cyan-300 font-medium tabular-nums ml-auto">
                {seatsNeeded}P
              </span>
            )}
            {shifted && (
              <span className={`text-[9px] text-indigo-400 flex-shrink-0 ${seatsNeeded > 0 ? '' : 'ml-auto'}`}>
                -{item.time_shift_minutes}m
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

const ConnectionCard = ({ connection, isSelected, onClick }) => {
  const isRisk = connection.marginMinutes < 0;
  const isTight = connection.marginMinutes >= 0 && connection.marginMinutes <= 5;
  const statusClass = isRisk
    ? 'text-red-300'
    : (isTight ? 'text-amber-300' : 'text-zinc-400');

  return (
    <div
      onClick={onClick}
      className={`
        p-2.5 rounded-[10px] cursor-pointer transition-all duration-150 border
        ${isSelected
          ? 'bg-red-500/[0.12] border-red-300/[0.65] shadow-[0_0_0_1px_rgba(248,113,113,0.35)]'
          : 'bg-red-500/[0.05] border-red-500/[0.25] hover:bg-red-500/[0.09] hover:border-red-400/[0.45]'
        }
      `}
    >
      <div className="mb-2 flex items-center gap-2">
        <span className="text-[9px] uppercase tracking-[0.12em] text-red-300/90 font-semibold">Trayecto</span>
        <div className="flex-1 border-t-2 border-dashed border-red-400/80" />
      </div>
      <div className="flex items-center gap-2.5">
        <div className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 bg-red-500/[0.2] text-red-200">
          <span className="text-[10px] font-semibold">-&gt;</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-medium text-zinc-300 truncate">
              {connection.fromRouteId} -&gt; {connection.toRouteId}
            </span>
            <span className="text-[10px] text-zinc-600 tabular-nums flex-shrink-0">
              {connection.endTime} - {connection.startTime}
            </span>
          </div>
          <div className={`mt-0.5 text-[10px] tabular-nums ${statusClass}`}>
            Pos. {connection.requiredMinutes}m | Ventana {connection.availableMinutes}m | Margen {connection.marginMinutes >= 0 ? '+' : ''}{connection.marginMinutes}m
          </div>
        </div>
      </div>
    </div>
  );
};

const BusCard = ({ bus, isSelected, isExpanded, onToggle, selectedRouteId, onRouteSelect, onConnectionSelect, routeCapacityById }) => {
  const color = getBusColor(bus.bus_id);
  const assignedVehicleCode = bus.assigned_vehicle_code || '';
  const assignedVehiclePlate = bus.assigned_vehicle_plate || '';
  const assignedSeatsMin = Number(bus.assigned_vehicle_seats_min || 0);
  const assignedSeatsMax = Number(bus.assigned_vehicle_seats_max || 0);
  const hasAssignedVehicle = Boolean(bus.uses_fleet_profile && (assignedVehicleCode || assignedVehiclePlate));
  const displayBusId = hasAssignedVehicle ? (assignedVehicleCode || assignedVehiclePlate) : bus.bus_id;
  const orderedItems = useMemo(() => sortItemsByTimeAndNumber(bus.items || []), [bus.items]);
  const entries = useMemo(() => orderedItems.filter(i => i.type === 'entry'), [orderedItems]);
  const exits = useMemo(() => orderedItems.filter(i => i.type === 'exit'), [orderedItems]);
  const connections = useMemo(() => buildBusConnections(bus.bus_id, orderedItems), [bus.bus_id, orderedItems]);
  const minSeatsNeeded = useMemo(
    () => getBusMinSeats(orderedItems, routeCapacityById),
    [orderedItems, routeCapacityById]
  );
  const totalStops = orderedItems.reduce((sum, item) => sum + (item.stops?.length || 0), 0);

  return (
    <div className={`
      rounded-[14px] overflow-hidden transition-all duration-200 border control-card
      ${isSelected
        ? 'border-cyan-400/35 bg-cyan-500/[0.06]'
        : 'border-[#2b4056] hover:border-[#4f708b]'
      }
    `}>
      <div
        onClick={onToggle}
        className="p-3 cursor-pointer flex items-center gap-3 hover:bg-[#152230] transition-colors"
      >
        {/* Color indicator */}
        <div
          className="w-1 h-9 rounded-full flex-shrink-0"
          style={{ backgroundColor: color }}
        />

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <div className="min-w-0">
              <span className="text-[13px] font-medium text-white truncate">{displayBusId}</span>
              {hasAssignedVehicle && (
                <p className="text-[9px] text-zinc-500 mt-0.5 truncate">
                  Plan: {bus.bus_id}{assignedVehiclePlate ? ` · ${assignedVehiclePlate}` : ''}
                </p>
              )}
            </div>
            <div className="flex items-center gap-1.5 text-[10px]">
              {hasAssignedVehicle && assignedSeatsMax > 0 && (
                <span className="px-1.5 py-0.5 rounded-md bg-emerald-500/[0.12] text-emerald-300 font-medium">
                  FLOTA {assignedSeatsMin > 0 ? `${assignedSeatsMin}-` : ''}{assignedSeatsMax}P
                </span>
              )}
              {minSeatsNeeded > 0 && (
                <span className="px-1.5 py-0.5 rounded-md bg-cyan-500/[0.1] text-cyan-300 font-medium">
                  MIN {minSeatsNeeded}P
                </span>
              )}
              {entries.length > 0 && (
                <span className="px-1.5 py-0.5 rounded-md bg-indigo-500/[0.1] text-indigo-400 font-medium">
                  {entries.length}E
                </span>
              )}
              {exits.length > 0 && (
                <span className="px-1.5 py-0.5 rounded-md bg-amber-500/[0.1] text-amber-400 font-medium">
                  {exits.length}X
                </span>
              )}
            </div>
          </div>
          <MiniTimeline items={orderedItems} />
        </div>

        <div className="flex-shrink-0 text-zinc-600">
          {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </div>
      </div>

      {isExpanded && (
        <div className="px-3 pb-3 space-y-1 border-t border-white/[0.04] pt-2">
          {(entries.length > 0 || exits.length > 0) && (
            <p className="text-[9px] uppercase tracking-wider text-zinc-600 font-medium px-1 pt-1">
              Secuencia operativa
            </p>
          )}

          {orderedItems.map((item, idx) => (
            <React.Fragment key={`seq-${item.route_id}-${item.start_time}-${idx}`}>
              <RouteCard
                item={item}
                orderNumber={idx + 1}
                isSelected={selectedRouteId === item.route_id}
                routeCapacityMap={routeCapacityById}
                onClick={(e) => { e.stopPropagation(); onRouteSelect(item.route_id); }}
              />
              {idx < connections.length && (
                <ConnectionCard
                  connection={connections[idx]}
                  isSelected={selectedRouteId === connections[idx].id}
                  onClick={(e) => {
                    e.stopPropagation();
                    onConnectionSelect?.(connections[idx].id, bus.bus_id);
                  }}
                />
              )}
            </React.Fragment>
          ))}

          <div className="flex items-center gap-3 pt-2 px-1 text-[10px] text-zinc-600">
            <span>{totalStops} paradas</span>
            <span>{orderedItems.length || 0} rutas</span>
            {minSeatsNeeded > 0 && <span>min plazas {minSeatsNeeded}</span>}
          </div>
        </div>
      )}
    </div>
  );
};

const DAY_LABELS = { L: 'Lunes', M: 'Martes', Mc: 'Miércoles', X: 'Xoves', V: 'Venres' };

const BusListPanel = ({ schedule = [], routes = [], onBusSelect, selectedBusId, selectedRouteId, onRouteSelect, onExport, activeDay, onScheduleChange }) => {
  const [expandedBus, setExpandedBus] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState('list'); // 'list' | 'board'

  const toggleExpand = (busId) => {
    const newBusId = expandedBus === busId ? null : busId;
    setExpandedBus(newBusId);
    if (onBusSelect) onBusSelect(newBusId);
  };

  const filteredSchedule = useMemo(() => {
    const sortedByBus = [...schedule].sort((a, b) => {
      const busDiff = getBusOrderValue(a?.bus_id || '') - getBusOrderValue(b?.bus_id || '');
      if (busDiff !== 0) return busDiff;
      return String(a?.bus_id || '').localeCompare(String(b?.bus_id || ''), 'es', { sensitivity: 'base', numeric: true });
    });

    if (!searchQuery.trim()) return sortedByBus;
    const q = searchQuery.toLowerCase();
    return sortedByBus.filter(bus =>
      bus.bus_id.toLowerCase().includes(q) ||
      (bus.assigned_vehicle_code || '').toLowerCase().includes(q) ||
      (bus.assigned_vehicle_plate || '').toLowerCase().includes(q) ||
      bus.items?.some(item =>
        item.school_name?.toLowerCase().includes(q) ||
        item.route_id?.toLowerCase().includes(q)
      )
    );
  }, [schedule, searchQuery]);

  const routeCapacityById = useMemo(() => buildRouteCapacityMap(routes), [routes]);

  const handleConnectionSelect = (connectionId, busId) => {
    if (onBusSelect && busId) onBusSelect(busId);
    if (onRouteSelect) onRouteSelect(connectionId);
  };

  if (!schedule || schedule.length === 0) {
    return (
      <aside className="w-[320px] h-full min-h-0 control-panel rounded-[16px] flex items-center justify-center flex-shrink-0">
        <div className="text-center px-6">
          <p className="text-[13px] text-zinc-500 font-medium">Horario de Flota</p>
          <p className="text-[11px] text-zinc-600 mt-1">Los resultados aparecerán tras la optimización</p>
        </div>
      </aside>
    );
  }

  return (
    <aside className={`h-full min-h-0 control-panel rounded-[16px] flex flex-col flex-shrink-0 overflow-hidden transition-all duration-300 ${viewMode === 'board' ? 'flex-1 w-full' : 'w-[320px]'}`}>
      <div className="p-4 border-b border-[#2b4056] space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[13px] font-medium text-white">
              Flota {activeDay ? <span className="text-indigo-400 font-normal">· {DAY_LABELS[activeDay] || activeDay}</span> : ''}
            </p>
            <p className="text-[10px] text-zinc-600">{schedule.length} buses</p>
          </div>
          <div className="flex items-center gap-2">
            {/* View toggle */}
            <div className="flex items-center bg-white/[0.03] rounded-lg p-0.5 border border-white/[0.06]">
              <button
                onClick={() => setViewMode('list')}
                className={`p-1.5 rounded-md transition-colors ${viewMode === 'list' ? 'bg-white/[0.08] text-white' : 'text-zinc-500 hover:text-zinc-300'}`}
                title="Vista lista"
              >
                <List size={14} />
              </button>
              <button
                onClick={() => setViewMode('board')}
                className={`p-1.5 rounded-md transition-colors ${viewMode === 'board' ? 'bg-white/[0.08] text-white' : 'text-zinc-500 hover:text-zinc-300'}`}
                title="Vista tablero (Drag & Drop)"
              >
                <LayoutGrid size={14} />
              </button>
            </div>
            <button
              onClick={onExport}
              className="text-[11px] text-zinc-500 hover:text-indigo-400 flex items-center gap-1.5 transition-colors px-2.5 py-1.5 rounded-[8px] hover:bg-white/[0.04] border border-transparent hover:border-white/[0.06]"
            >
              <Download size={12} />
              Exportar PDF
            </button>
          </div>
        </div>

        <div className="relative">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-600" />
          <input
            type="text"
            placeholder="Buscar buses, colegios..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-8 py-2 text-[12px] bg-white/[0.03] border border-white/[0.06] rounded-[10px] text-zinc-300 placeholder-zinc-600 focus:outline-none focus:border-white/[0.12] transition-colors"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-600 hover:text-zinc-400"
            >
              <X size={13} />
            </button>
          )}
        </div>
      </div>

      {viewMode === 'list' ? (
        <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-1.5">
          {filteredSchedule.map((bus) => (
            <BusCard
              key={bus.bus_id}
              bus={bus}
              isSelected={selectedBusId === bus.bus_id}
              isExpanded={expandedBus === bus.bus_id}
              onToggle={() => toggleExpand(bus.bus_id)}
              selectedRouteId={selectedRouteId}
              onRouteSelect={onRouteSelect}
              onConnectionSelect={handleConnectionSelect}
              routeCapacityById={routeCapacityById}
            />
          ))}
          {filteredSchedule.length === 0 && searchQuery && (
            <p className="text-[12px] text-zinc-600 text-center py-8">Sin resultados</p>
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-hidden p-4">
          <DraggableSchedule
            schedule={filteredSchedule}
            onScheduleChange={(newSchedule) => {
              if (onScheduleChange) onScheduleChange(newSchedule);
            }}
            selectedRouteId={selectedRouteId}
            onRouteSelect={onRouteSelect}
          />
        </div>
      )}
    </aside>
  );
};

export default BusListPanel;
