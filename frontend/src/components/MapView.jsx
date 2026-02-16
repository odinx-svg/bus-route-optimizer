import React, { useMemo, useState, useEffect } from 'react';
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap, ZoomControl, Pane } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { fetchRouteGeometry, fetchConnectionGeometry, isGeometryCached } from '../services/RouteService';
import { Loader2 } from 'lucide-react';
import RouteStopsLayer from './RouteStopsLayer';

const BUS_COLORS = [
  '#6366F1', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899',
  '#06B6D4', '#F97316', '#84CC16', '#14B8A6', '#EF4444',
  '#818CF8', '#22D3EE', '#A3E635', '#FB923C', '#E879F9',
];

const getBusColor = (id) => {
  const num = parseInt(id.replace(/\D/g, ''), 10) || 0;
  return BUS_COLORS[num % BUS_COLORS.length];
};

const parseTimeToMinutes = (value) => {
  if (!value) return 0;
  const [h = 0, m = 0] = String(value).split(':').map(v => Number(v) || 0);
  return (h * 60) + m;
};

const getRouteOrderValue = (routeId) => {
  const match = String(routeId || '').match(/\d+/);
  if (!match) return Number.MAX_SAFE_INTEGER;
  const parsed = Number(match[0]);
  return Number.isFinite(parsed) ? parsed : Number.MAX_SAFE_INTEGER;
};

const sortItemsByTimeAndNumber = (items = []) => {
  return [...(items || [])].sort((a, b) => {
    const startDiff = parseTimeToMinutes(a?.start_time) - parseTimeToMinutes(b?.start_time);
    if (startDiff !== 0) return startDiff;
    const routeDiff = getRouteOrderValue(a?.route_id) - getRouteOrderValue(b?.route_id);
    if (routeDiff !== 0) return routeDiff;
    return String(a?.route_id || '').localeCompare(String(b?.route_id || ''), 'es', { sensitivity: 'base', numeric: true });
  });
};

const pickMatchedRouteIndex = (busRoutes = [], item = {}, usedIndexes = new Set()) => {
  const targetRouteId = String(item?.route_id || '');
  const targetStart = parseTimeToMinutes(item?.start_time);
  const targetEnd = parseTimeToMinutes(item?.end_time);

  let idx = busRoutes.findIndex((route, routeIdx) => {
    if (usedIndexes.has(routeIdx)) return false;
    return (
      String(route?.routeId || '') === targetRouteId &&
      parseTimeToMinutes(route?.startTime) === targetStart &&
      parseTimeToMinutes(route?.endTime) === targetEnd
    );
  });
  if (idx >= 0) return idx;

  idx = busRoutes.findIndex((route, routeIdx) => (
    !usedIndexes.has(routeIdx) && String(route?.routeId || '') === targetRouteId
  ));
  if (idx >= 0) return idx;

  idx = busRoutes.findIndex((_, routeIdx) => !usedIndexes.has(routeIdx));
  return idx;
};

const matchRoutesToItems = (sortedItems = [], busRoutes = []) => {
  const used = new Set();
  return sortedItems.map((item) => {
    const idx = pickMatchedRouteIndex(busRoutes, item, used);
    if (idx < 0) return null;
    used.add(idx);
    return busRoutes[idx];
  });
};

const buildConnectionSelectionId = (busId, fromRouteId, toRouteId, index) => (
  `conn:${encodeURIComponent(String(busId || ''))}:${encodeURIComponent(String(fromRouteId || ''))}:${encodeURIComponent(String(toRouteId || ''))}:${index}`
);

const parseConnectionSelectionId = (value) => {
  if (typeof value !== 'string' || !value.startsWith('conn:')) return null;
  const parts = value.split(':');
  if (parts.length !== 5) return null;

  const index = Number(parts[4]);
  if (!Number.isFinite(index)) return null;

  try {
    return {
      busId: decodeURIComponent(parts[1]),
      fromRouteId: decodeURIComponent(parts[2]),
      toRouteId: decodeURIComponent(parts[3]),
      index,
      id: value,
    };
  } catch {
    return null;
  }
};

const getPositioningMinutes = (item) => {
  const raw = item?.positioning_minutes ?? item?.deadhead_minutes ?? item?.deadhead ?? 0;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? Math.max(0, Math.round(parsed)) : 0;
};

const createSchoolIcon = (name) => {
  return L.divIcon({
    className: 'school-marker',
    html: `<div style="
      background: #1c1c1f;
      color: #22C55E;
      border-radius: 8px;
      padding: 3px 8px;
      font-size: 10px;
      font-weight: 600;
      white-space: nowrap;
      border: 1px solid rgba(34, 197, 94, 0.25);
      box-shadow: 0 2px 8px rgba(0,0,0,0.4);
      max-width: 120px;
      overflow: hidden;
      text-overflow: ellipsis;
    ">${name}</div>`,
    iconSize: [0, 0],
    iconAnchor: [0, 16],
  });
};

const createRouteOrderIcon = (order, highlighted = false) => {
  const bg = highlighted ? 'rgba(239, 68, 68, 0.95)' : 'rgba(15, 23, 42, 0.92)';
  const border = highlighted ? '1px solid rgba(254, 202, 202, 0.9)' : '1px solid rgba(125, 211, 252, 0.55)';
  return L.divIcon({
    className: 'route-order-marker',
    html: `<div style="
      width: 20px;
      height: 20px;
      border-radius: 999px;
      background: ${bg};
      color: #f8fafc;
      border: ${border};
      font-size: 11px;
      font-weight: 700;
      line-height: 18px;
      text-align: center;
      box-shadow: 0 1px 6px rgba(0,0,0,0.45);
      font-family: 'Inter', sans-serif;
    ">${order}</div>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });
};

function MapBounds({ routes }) {
  const map = useMap();
  useEffect(() => {
    if (routes && routes.length > 0) {
      const allCoords = routes.flatMap(r => r.positions || []).filter(p => p && p.length === 2);
      if (allCoords.length > 0) {
        try {
          const bounds = L.latLngBounds(allCoords);
          map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15, animate: true, duration: 0.4 });
        } catch (e) {
          console.error('Error fitting bounds:', e);
        }
      }
    }
  }, [map, routes]);
  return null;
}

const MapView = ({ routes, schedule, selectedBusId, selectedRouteId, onBusSelect }) => {
  const [mapRoutes, setMapRoutes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadProgress, setLoadProgress] = useState(0);
  const [deadheadPaths, setDeadheadPaths] = useState([]);
  const selectedConnection = useMemo(
    () => parseConnectionSelectionId(selectedRouteId),
    [selectedRouteId],
  );
  const selectedRouteBusId = useMemo(() => {
    if (selectedConnection?.id) return selectedConnection.busId;
    if (!selectedRouteId || String(selectedRouteId).startsWith('conn:')) return null;
    const matchedRoute = mapRoutes.find((route) => String(route?.routeId || '') === String(selectedRouteId));
    return matchedRoute?.busId || null;
  }, [selectedConnection, selectedRouteId, mapRoutes]);
  const effectiveSelectedBusId = selectedConnection?.busId || selectedBusId || selectedRouteBusId;

  const busColors = useMemo(() => {
    if (!schedule) return {};
    const colors = {};
    schedule.forEach(bus => { colors[bus.bus_id] = getBusColor(bus.bus_id); });
    return colors;
  }, [schedule]);

  useEffect(() => {
    let isMounted = true;

    const loadRoutes = async () => {
      if (!schedule || !routes || schedule.length === 0) {
        setMapRoutes([]);
        return;
      }

      // Count how many routes actually need fetching vs cached
      let needsFetch = 0;
      let totalItems = 0;
      for (const bus of schedule) {
        for (const item of bus.items || []) {
          totalItems++;
          const route = routes.find(r => r.id === item.route_id);
            if (route?.stops?.length > 0 && !isGeometryCached(item.route_id, route.stops)) {
            needsFetch++;
          }
        }
      }

      // Only show loading spinner if we actually need to fetch routes
      const showLoading = needsFetch > 0;
      if (showLoading) {
        setLoading(true);
        setLoadProgress(0);
      }

      const routeData = [];
      let loaded = 0;

      for (const bus of schedule) {
        const color = busColors[bus.bus_id];
        for (const item of bus.items || []) {
          const route = routes.find(r => r.id === item.route_id);
          if (route?.stops?.length > 0) {
            try {
              // Pass routeId for caching
              const positions = await fetchRouteGeometry(route.stops, item.route_id);
              if (isMounted && positions.length > 0) {
                routeData.push({
                  busId: bus.bus_id,
                  routeId: route.id,
                  type: item.type,
                  color,
                  positions,
                  school: route.school_name,
                  stops: route.stops,
                  startTime: item.start_time,
                  endTime: item.end_time,
                  timeShift: item.time_shift_minutes,
                });
              }
            } catch (e) {
              if (isMounted) {
                routeData.push({
                  busId: bus.bus_id,
                  routeId: route.id,
                  type: item.type,
                  color,
                  positions: route.stops.map(s => [s.lat, s.lon]),
                  school: route.school_name,
                  stops: route.stops,
                  startTime: item.start_time,
                  endTime: item.end_time,
                  timeShift: item.time_shift_minutes,
                });
              }
            }
          }
          loaded++;
          if (isMounted && showLoading && totalItems > 0) {
            setLoadProgress(Math.round((loaded / totalItems) * 100));
          }
        }
      }

      if (isMounted) {
        setMapRoutes(routeData);
        setLoading(false);
      }
    };

    loadRoutes();
    return () => { isMounted = false; };
  }, [routes, schedule, busColors]);

  const displayedRoutes = useMemo(() => {
    // For connection focus, show ONLY the deadhead path (no route polylines).
    if (selectedConnection?.id) return [];
    // For route focus, show ONLY that route.
    if (selectedRouteId && !String(selectedRouteId).startsWith('conn:')) {
      return mapRoutes.filter(r => String(r.routeId || '') === String(selectedRouteId));
    }
    // For bus focus, show ALL routes of that bus.
    if (effectiveSelectedBusId) return mapRoutes.filter(r => r.busId === effectiveSelectedBusId);
    // No focus => show all routes.
    return mapRoutes;
  }, [mapRoutes, selectedConnection, selectedRouteId, effectiveSelectedBusId]);

  const dimmedRoutes = useMemo(() => {
    // In focused mode we do not render "background" routes to avoid visual noise.
    if (selectedConnection?.id || selectedRouteId || effectiveSelectedBusId) return [];
    if (!effectiveSelectedBusId && !selectedRouteId) return [];
    return [];
  }, [mapRoutes, selectedConnection, selectedRouteId, effectiveSelectedBusId]);

  const fallbackDeadheadPaths = useMemo(() => {
    if (!effectiveSelectedBusId) return [];
    const bus = schedule?.find((b) => b.bus_id === effectiveSelectedBusId);
    if (!bus?.items || bus.items.length < 2) return [];

    const sortedItems = sortItemsByTimeAndNumber(bus.items || []);
    const busRoutes = mapRoutes
      .filter((route) => route.busId === effectiveSelectedBusId)
      .sort((a, b) => {
        const startDiff = parseTimeToMinutes(a.startTime) - parseTimeToMinutes(b.startTime);
        if (startDiff !== 0) return startDiff;
        return String(a.routeId || '').localeCompare(String(b.routeId || ''), 'es', { sensitivity: 'base', numeric: true });
      });
    const matchedRoutes = matchRoutesToItems(sortedItems, busRoutes);

    const paths = [];
    for (let i = 0; i < sortedItems.length - 1; i++) {
      const currentItem = sortedItems[i];
      const nextItem = sortedItems[i + 1];
      const currentRoute = matchedRoutes[i];
      const nextRoute = matchedRoutes[i + 1];
      const fallbackFrom = currentRoute?.positions?.[currentRoute.positions.length - 1];
      const fallbackTo = nextRoute?.positions?.[0];
      if (!fallbackFrom || !fallbackTo) continue;

      paths.push({
        id: `${currentItem.route_id}-${nextItem.route_id}-${i}`,
        selectionId: buildConnectionSelectionId(
          effectiveSelectedBusId,
          currentItem.route_id,
          nextItem.route_id,
          i,
        ),
        fromRouteId: currentItem.route_id,
        toRouteId: nextItem.route_id,
        positions: [fallbackFrom, fallbackTo],
        minutes: getPositioningMinutes(nextItem),
        endTime: currentItem.end_time,
        startTime: nextItem.start_time,
      });
    }

    return paths;
  }, [effectiveSelectedBusId, schedule, mapRoutes]);

  useEffect(() => {
    let isMounted = true;

    const loadDeadheadPaths = async () => {
      if (!effectiveSelectedBusId) {
        if (isMounted) setDeadheadPaths([]);
        return;
      }

      const bus = schedule?.find(b => b.bus_id === effectiveSelectedBusId);
      if (!bus?.items || bus.items.length < 2) {
        if (isMounted) setDeadheadPaths([]);
        return;
      }

      const sortedItems = sortItemsByTimeAndNumber(bus.items || []);
      const busRoutes = mapRoutes
        .filter(r => r.busId === effectiveSelectedBusId)
        .sort((a, b) => {
          const startDiff = parseTimeToMinutes(a.startTime) - parseTimeToMinutes(b.startTime);
          if (startDiff !== 0) return startDiff;
          return String(a.routeId || '').localeCompare(String(b.routeId || ''), 'es', { sensitivity: 'base', numeric: true });
        });
      const matchedRoutes = matchRoutesToItems(sortedItems, busRoutes);

      const pathPromises = [];
      for (let i = 0; i < sortedItems.length - 1; i++) {
        const currentItem = sortedItems[i];
        const nextItem = sortedItems[i + 1];
        const currentRoute = matchedRoutes[i];
        const nextRoute = matchedRoutes[i + 1];
        if (!currentRoute || !nextRoute) continue;

        const endStop = currentRoute.stops?.[currentRoute.stops.length - 1];
        const startStop = nextRoute.stops?.[0];
        const fallbackFrom = currentRoute.positions?.[currentRoute.positions.length - 1];
        const fallbackTo = nextRoute.positions?.[0];
        const cacheKey = `deadhead:${effectiveSelectedBusId}:${currentItem.route_id}->${nextItem.route_id}:${i}`;
        const selectionId = buildConnectionSelectionId(
          effectiveSelectedBusId,
          currentItem.route_id,
          nextItem.route_id,
          i,
        );

        pathPromises.push((async () => {
          let positions = [];
          if (endStop && startStop) {
            positions = await fetchConnectionGeometry(
              { lat: endStop.lat, lon: endStop.lon ?? endStop.lng },
              { lat: startStop.lat, lon: startStop.lon ?? startStop.lng },
              cacheKey,
            );
          }

          if ((!positions || positions.length < 2) && fallbackFrom && fallbackTo) {
            positions = [fallbackFrom, fallbackTo];
          }

          if (!positions || positions.length < 2) return null;
          return {
            id: `${currentItem.route_id}-${nextItem.route_id}-${i}`,
            selectionId,
            fromRouteId: currentItem.route_id,
            toRouteId: nextItem.route_id,
            positions,
            minutes: getPositioningMinutes(nextItem),
            endTime: currentItem.end_time,
            startTime: nextItem.start_time,
          };
        })());
      }

      const loadedPaths = (await Promise.all(pathPromises)).filter(Boolean);
      if (isMounted) {
        setDeadheadPaths(loadedPaths);
      }
    };

    loadDeadheadPaths();
    return () => { isMounted = false; };
  }, [effectiveSelectedBusId, schedule, mapRoutes]);

  const routeOrderMarkers = useMemo(() => {
    if (!effectiveSelectedBusId) return [];
    if (selectedConnection?.id) return [];
    if (selectedRouteId && !String(selectedRouteId).startsWith('conn:')) return [];
    const bus = schedule?.find(b => b.bus_id === effectiveSelectedBusId);
    if (!bus?.items?.length) return [];

    const sortedItems = sortItemsByTimeAndNumber(bus.items || []);
    const busRoutes = mapRoutes
      .filter(r => r.busId === effectiveSelectedBusId)
      .sort((a, b) => {
        const startDiff = parseTimeToMinutes(a.startTime) - parseTimeToMinutes(b.startTime);
        if (startDiff !== 0) return startDiff;
        return String(a.routeId || '').localeCompare(String(b.routeId || ''), 'es', { sensitivity: 'base', numeric: true });
      });
    const matchedRoutes = matchRoutesToItems(sortedItems, busRoutes);
    const markers = [];

    sortedItems.forEach((item, idx) => {
      const route = matchedRoutes[idx];
      if (!route?.positions?.length) return;
      const markerPoint = route.positions[Math.floor(route.positions.length * 0.35)] || route.positions[0];
      if (!markerPoint) return;

      markers.push({
        id: `ord-${route.routeId}-${idx}`,
        routeId: route.routeId,
        order: idx + 1,
        position: markerPoint,
        startTime: item.start_time,
        endTime: item.end_time,
      });
    });

    if (selectedConnection?.id) {
      const involvedRoutes = new Set([selectedConnection.fromRouteId, selectedConnection.toRouteId]);
      return markers.filter((marker) => involvedRoutes.has(String(marker.routeId || '')));
    }

    return markers;
  }, [effectiveSelectedBusId, schedule, mapRoutes, selectedConnection, selectedRouteId]);

  const schoolMarkers = useMemo(() => {
    const schools = {};
    for (const route of displayedRoutes) {
      const schoolStop = route.stops?.find(s => s.is_school);
      if (schoolStop && route.school) {
        const key = `${schoolStop.lat.toFixed(4)},${schoolStop.lon.toFixed(4)}`;
        if (!schools[key]) {
          schools[key] = { lat: schoolStop.lat, lon: schoolStop.lon, name: route.school };
        }
      }
    }
    return Object.values(schools);
  }, [displayedRoutes]);

  const showStopMarkers = !selectedConnection?.id && (effectiveSelectedBusId || selectedRouteId);
  const allDeadheadPaths = useMemo(() => {
    if (!fallbackDeadheadPaths.length) return deadheadPaths;

    const byId = new Map();
    for (const path of fallbackDeadheadPaths) {
      byId.set(path.id, path);
    }
    for (const path of deadheadPaths) {
      const previous = byId.get(path.id);
      if (!previous) {
        byId.set(path.id, path);
        continue;
      }
      byId.set(path.id, {
        ...previous,
        ...path,
        positions: path?.positions?.length >= 2 ? path.positions : previous.positions,
      });
    }
    return Array.from(byId.values());
  }, [fallbackDeadheadPaths, deadheadPaths]);

  const visibleDeadheadPaths = useMemo(() => {
    if (selectedRouteId && !String(selectedRouteId).startsWith('conn:')) return [];
    if (!selectedConnection?.id) return allDeadheadPaths;
    return allDeadheadPaths.filter((path) => path.selectionId === selectedConnection.id);
  }, [allDeadheadPaths, selectedConnection, selectedRouteId]);
  const center = [42.23, -8.72];

  return (
    <div className="h-full w-full relative bg-[#0e0e10] rounded-[16px] overflow-hidden border border-white/[0.06]">
      <MapContainer
        center={center}
        zoom={12}
        style={{ height: '100%', width: '100%', background: '#0e0e10' }}
        zoomControl={false}
      >
        <TileLayer
          attribution='&copy; OpenStreetMap'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        <Pane name="deadheadPane" style={{ zIndex: 470 }} />
        <ZoomControl position="bottomright" />
        <MapBounds routes={displayedRoutes} />

        {/* Dimmed routes */}
        {dimmedRoutes.map((route, idx) => (
          <Polyline
            key={`dim-${idx}`}
            positions={route.positions}
            pathOptions={{
              color: route.color,
              weight: 2,
              opacity: 0.1,
              lineCap: 'round',
              lineJoin: 'round',
            }}
          />
        ))}

        {/* Route order markers for selected bus */}
        {routeOrderMarkers.map((marker) => (
          <Marker
            key={marker.id}
            position={marker.position}
            icon={createRouteOrderIcon(marker.order, selectedRouteId === marker.routeId)}
          >
            <Popup>
              <div className="text-xs min-w-[150px]">
                <p className="font-semibold text-sm text-zinc-100">Ruta #{marker.order}</p>
                <p className="text-zinc-400 mt-1">{marker.routeId}</p>
                <p className="text-zinc-500">{marker.startTime} - {marker.endTime}</p>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* Route stops with enhanced markers - incluye linea real por carretera + paradas */}
        {showStopMarkers ? (
          <RouteStopsLayer
            routes={displayedRoutes}
            selectedBusId={effectiveSelectedBusId}
            selectedRouteId={selectedRouteId}
            onBusSelect={onBusSelect}
          />
        ) : (
          /* Active routes - simplified polyline (solo cuando NO se muestran marcadores) */
          displayedRoutes.map((route, idx) => (
            <Polyline
              key={`route-${idx}`}
              positions={route.positions}
              pathOptions={{
                color: route.color,
                weight: selectedRouteId === route.routeId ? 5 : 3.5,
                opacity: (effectiveSelectedBusId || selectedRouteId) ? 0.9 : 0.55,
                lineCap: 'round',
                lineJoin: 'round',
              }}
              eventHandlers={{
                click: () => onBusSelect && onBusSelect(route.busId),
              }}
            >
              <Popup>
                <div className="text-xs min-w-[140px]">
                  <p className="font-semibold text-sm">{route.routeId}</p>
                  <p className="text-zinc-400">{route.school}</p>
                  <p className="text-zinc-500 mt-1">Bus: {route.busId}</p>
                  <p className="text-zinc-500">{route.startTime} - {route.endTime}</p>
                  {route.timeShift > 0 && (
                    <p className="text-indigo-400 mt-1">Adelantado -{route.timeShift} min</p>
                  )}
                </div>
              </Popup>
            </Polyline>
          ))
        )}

        {/* Deadhead paths (between end of route N and start of route N+1) */}
        {visibleDeadheadPaths.map((path, idx) => {
          const isFocused = selectedConnection?.id === path.selectionId;
          return (
            <Polyline
              key={`dh-${path.id || idx}`}
              pane="deadheadPane"
              positions={path.positions}
              pathOptions={{
                color: '#ef4444',
                weight: isFocused ? 5 : 4,
                opacity: isFocused ? 0.95 : 0.78,
                dashArray: '8, 8',
                lineCap: 'round',
              }}
            >
              <Popup>
                <div className="text-xs min-w-[180px]">
                  <p className="font-semibold text-sm text-zinc-100">Posicionamiento</p>
                  <p className="text-zinc-400 mt-1">{path.fromRouteId} -&gt; {path.toRouteId}</p>
                  <p className="text-zinc-500">{path.endTime} -&gt; {path.startTime}</p>
                  <p className="text-zinc-300 mt-1">Tiempo estimado: {path.minutes} min</p>
                </div>
              </Popup>
            </Polyline>
          );
        })}

        {/* School markers */}
        {showStopMarkers && schoolMarkers.map((school, idx) => (
          <Marker
            key={`school-${idx}`}
            position={[school.lat, school.lon]}
            icon={createSchoolIcon(school.name)}
          />
        ))}
      </MapContainer>

      {/* Loading overlay */}
      {loading && (
        <div className="absolute inset-0 bg-[#0e0e10]/70 backdrop-blur-sm flex items-center justify-center z-[1000]">
          <div className="bg-[#1c1c1f] border border-white/[0.08] p-5 rounded-[14px] flex flex-col items-center gap-3 min-w-[180px]">
            <Loader2 className="w-5 h-5 text-indigo-400 animate-spin" />
            <span className="text-[12px] font-medium text-white">Cargando rutas</span>
            <div className="w-full h-[3px] bg-white/[0.06] rounded-full overflow-hidden">
              <div
                className="h-full bg-indigo-500 rounded-full transition-all duration-300"
                style={{ width: `${loadProgress}%` }}
              />
            </div>
            <span className="text-[10px] text-zinc-600 tabular-nums">{loadProgress}%</span>
          </div>
        </div>
      )}

      {/* Info overlay */}
      <div className="absolute top-3 left-3 z-[999]">
        <div className="bg-[#1c1c1f]/92 backdrop-blur-md border border-white/[0.06] px-3 py-2 rounded-[10px]">
          <span className="text-[11px] font-medium text-white">
            {effectiveSelectedBusId || 'Todas las Rutas'}
          </span>
          {effectiveSelectedBusId && (
            <p className="text-[10px] text-zinc-500 mt-0.5">
              {displayedRoutes.length} ruta{displayedRoutes.length !== 1 ? 's' : ''}
              {selectedConnection?.id
                ? ` | Posicionamiento ${selectedConnection.fromRouteId}->${selectedConnection.toRouteId}`
                : (selectedRouteId ? ` | ${selectedRouteId}` : '')}
            </p>
          )}
          {!effectiveSelectedBusId && mapRoutes.length > 0 && (
            <p className="text-[10px] text-zinc-500 mt-0.5">
              {mapRoutes.length} rutas | {schedule?.length || 0} buses
            </p>
          )}
        </div>
      </div>

      {/* Legend */}
      {(effectiveSelectedBusId || mapRoutes.length > 0) && (
        <div className="absolute bottom-3 left-3 z-[999]">
          <div className="bg-[#1c1c1f]/92 backdrop-blur-md border border-white/[0.06] px-3 py-2 rounded-[10px] flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-[3px] bg-indigo-400 rounded-full" />
              <span className="text-[10px] text-zinc-400">Entrada</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-[3px] bg-amber-400 rounded-full" />
              <span className="text-[10px] text-zinc-400">Salida</span>
            </div>
            {effectiveSelectedBusId && (
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-[3px] border-t border-dashed border-red-400/70" />
                <span className="text-[10px] text-zinc-400">En vacio</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default MapView;

