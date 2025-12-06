import React, { useMemo, useState, useEffect } from 'react';
import { MapContainer, TileLayer, Polyline, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { fetchRouteGeometry } from '../services/RouteService';

// Fix for default marker icon
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

const getRandomColor = (id) => {
    const colors = [
        '#FF5733', '#33FF57', '#3357FF', '#FF33A1', '#A133FF',
        '#33FFF5', '#FFC300', '#C70039', '#900C3F', '#581845'
    ];
    let hash = 0;
    for (let i = 0; i < id.length; i++) {
        hash = id.charCodeAt(i) + ((hash << 5) - hash);
    }
    return colors[Math.abs(hash) % colors.length];
};

const MapView = ({ routes, schedule }) => {
    const [mapData, setMapData] = useState([]);
    const [loading, setLoading] = useState(false);
    const [hoveredBusId, setHoveredBusId] = useState(null);
    const [selectedBus, setSelectedBus] = useState(null);

    // Calculate center based on the first available position
    const center = useMemo(() => {
        if (mapData.length > 0 && mapData[0].positions.length > 0) {
            return mapData[0].positions[0];
        }
        return [42.8782, -8.5448]; // Default to Santiago de Compostela
    }, [mapData]);

    const metrics = useMemo(() => {
        if (!schedule || schedule.length === 0) return null;

        let totalRoutes = 0;
        let totalDeadhead = 0;
        let totalServiceTime = 0;

        const parseTime = (t) => {
            if (!t) return 0;
            const [h, m] = t.split(':').map(Number);
            return h * 60 + m;
        };

        schedule.forEach(bus => {
            totalRoutes += bus.items.length;
            bus.items.forEach(item => {
                totalDeadhead += (item.deadhead_minutes || 0);
                totalServiceTime += (parseTime(item.end_time) - parseTime(item.start_time));
            });
        });

        const avgRoutes = (totalRoutes / schedule.length).toFixed(1);
        const efficiency = totalServiceTime > 0
            ? ((totalServiceTime / (totalServiceTime + totalDeadhead)) * 100).toFixed(1)
            : 0;

        return {
            totalBuses: schedule.length,
            totalRoutes,
            avgRoutes,
            totalDeadhead,
            efficiency
        };
    }, [schedule]);

    useEffect(() => {
        const loadRoutes = async () => {
            if (!schedule || !routes) return;

            setLoading(true);
            const data = [];

            // Process all buses and their items
            for (const bus of schedule) {
                const color = getRandomColor(bus.bus_id);

                for (const item of bus.items) {
                    const route = routes.find(r => r.id === item.route_id);
                    if (route && route.stops && route.stops.length > 0) {
                        // Fetch real geometry
                        const positions = await fetchRouteGeometry(route.stops);

                        data.push({
                            busId: bus.bus_id,
                            routeId: route.id,
                            color: color,
                            positions: positions,
                            start: route.stops[0].name,
                            end: route.stops[route.stops.length - 1].name,
                            startTime: item.start_time,
                            endTime: item.end_time,
                            originalStart: item.original_start_time,
                            shift: item.time_shift_minutes,
                            type: item.type
                        });
                    }
                }
            }

            setMapData(data);
            setLoading(false);
        };

        loadRoutes();
    }, [routes, schedule]);

    // Update selected bus info when hovering
    useEffect(() => {
        if (hoveredBusId) {
            const busSchedule = schedule.find(b => b.bus_id === hoveredBusId);
            setSelectedBus(busSchedule);
        } else {
            setSelectedBus(null);
        }
    }, [hoveredBusId, schedule]);

    return (
        <div className="h-full w-full relative flex bg-slate-900 overflow-hidden">
            {/* Left Sidebar: Bus List */}
            <div className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col z-10 shadow-xl">
                <div className="p-4 border-b border-slate-800 bg-slate-900/50 backdrop-blur">
                    <h2 className="text-xl font-bold text-white flex items-center gap-2 mb-4">
                        <span className="w-2 h-6 bg-indigo-500 rounded-full"></span>
                        Fleet Metrics
                    </h2>

                    {metrics && (
                        <div className="grid grid-cols-2 gap-2">
                            <div className="bg-slate-800/50 p-2 rounded-lg border border-slate-700/50">
                                <p className="text-xs text-slate-400 uppercase">Buses</p>
                                <p className="text-lg font-bold text-white">{metrics.totalBuses}</p>
                            </div>
                            <div className="bg-slate-800/50 p-2 rounded-lg border border-slate-700/50">
                                <p className="text-xs text-slate-400 uppercase">Avg Routes</p>
                                <p className="text-lg font-bold text-emerald-400">{metrics.avgRoutes}</p>
                            </div>
                            <div className="bg-slate-800/50 p-2 rounded-lg border border-slate-700/50">
                                <p className="text-xs text-slate-400 uppercase">Deadhead</p>
                                <p className="text-lg font-bold text-amber-400">{metrics.totalDeadhead}m</p>
                            </div>
                            <div className="bg-slate-800/50 p-2 rounded-lg border border-slate-700/50">
                                <p className="text-xs text-slate-400 uppercase">Efficiency</p>
                                <p className="text-lg font-bold text-indigo-400">{metrics.efficiency}%</p>
                            </div>
                        </div>
                    )}
                </div>

                <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-2">
                    {schedule && schedule.map((bus) => {
                        const isSelected = selectedBus?.bus_id === bus.bus_id;
                        return (
                            <button
                                key={bus.bus_id}
                                onClick={() => setSelectedBus(bus)}
                                className={`w-full text-left p-3 rounded-xl transition-all duration-200 border ${isSelected
                                    ? 'bg-indigo-600/20 border-indigo-500/50 shadow-lg shadow-indigo-900/20'
                                    : 'bg-slate-800/50 border-slate-700/50 hover:bg-slate-800 hover:border-slate-600'
                                    }`}
                            >
                                <div className="flex justify-between items-center mb-1">
                                    <span className={`font-bold ${isSelected ? 'text-white' : 'text-slate-200'}`}>
                                        {bus.bus_id}
                                    </span>
                                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${isSelected ? 'bg-indigo-500 text-white' : 'bg-slate-700 text-slate-400'
                                        }`}>
                                        {bus.items.length} routes
                                    </span>
                                </div>
                                <div className="flex items-center gap-2 text-xs text-slate-400">
                                    <span className="truncate max-w-[120px]">
                                        {bus.items[0].start_time} - {bus.items[bus.items.length - 1].end_time}
                                    </span>
                                </div>
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Center: Map */}
            <div className="flex-1 h-full relative z-0">
                {loading && (
                    <div className="absolute inset-0 z-[1000] bg-slate-900/50 backdrop-blur-sm flex items-center justify-center">
                        <div className="text-white font-bold text-xl flex items-center">
                            <svg className="animate-spin -ml-1 mr-3 h-8 w-8 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            Loading Real Paths...
                        </div>
                    </div>
                )}
                <MapContainer center={center} zoom={12} style={{ height: '100%', width: '100%' }}>
                    <TileLayer
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    />
                    {mapData.map((item, idx) => {
                        // Only show selected bus or all if none selected?
                        // User asked for list on left, click -> show routes.
                        // Let's show ALL routes dimmed, and selected one highlighted.

                        const isSelected = selectedBus?.bus_id === item.busId;
                        const isHovered = hoveredBusId === item.busId;

                        // If a bus is selected, dim others significantly
                        const isDimmed = selectedBus && !isSelected;

                        // Z-index: Selected on top
                        const zIndex = isSelected ? 1000 : 1;

                        return (
                            <React.Fragment key={`${item.busId}-${item.routeId}-${idx}`}>
                                <Polyline
                                    positions={item.positions}
                                    pathOptions={{
                                        color: isSelected ? '#6366f1' : (isDimmed ? '#334155' : item.color), // Indigo if selected, Slate if dimmed, else Random
                                        weight: isSelected ? 6 : (isDimmed ? 2 : 4),
                                        opacity: isSelected ? 1 : (isDimmed ? 0.2 : 0.6),
                                        zIndex: zIndex
                                    }}
                                    eventHandlers={{
                                        click: () => {
                                            const bus = schedule.find(b => b.bus_id === item.busId);
                                            setSelectedBus(bus);
                                        },
                                        mouseover: () => setHoveredBusId(item.busId),
                                        mouseout: () => setHoveredBusId(null)
                                    }}
                                >
                                    <Popup>
                                        <div className="text-gray-800">
                                            <strong>Bus: {item.busId}</strong><br />
                                            Route: {item.routeId}
                                        </div>
                                    </Popup>
                                </Polyline>

                                {/* Show markers ONLY for selected bus to avoid clutter */}
                                {isSelected && item.positions.length > 0 && (
                                    <>
                                        {/* Start Marker */}
                                        <Marker position={item.positions[0]}>
                                            <Popup>
                                                <strong>Start: {item.start}</strong><br />
                                                Time: {item.startTime}
                                            </Popup>
                                        </Marker>

                                        {/* End Marker */}
                                        <Marker position={item.positions[item.positions.length - 1]}>
                                            <Popup>
                                                <strong>End: {item.end}</strong><br />
                                                Time: {item.endTime}
                                            </Popup>
                                        </Marker>
                                    </>
                                )}
                            </React.Fragment>
                        );
                    })}
                </MapContainer>
            </div>

            {/* Right Sidebar: Route Details */}
            {selectedBus && (
                <div className="w-80 bg-slate-900 border-l border-slate-800 flex flex-col z-10 shadow-xl animate-in slide-in-from-right duration-300">
                    <div className="p-6 border-b border-slate-800 bg-slate-900/50 backdrop-blur">
                        <div className="flex items-center justify-between mb-2">
                            <h3 className="text-2xl font-bold text-white">Bus {selectedBus.bus_id}</h3>
                            <button
                                onClick={() => setSelectedBus(null)}
                                className="text-slate-400 hover:text-white transition-colors"
                            >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                        <div className="flex gap-2">
                            <span className="px-2 py-1 rounded text-xs font-medium bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                                {selectedBus.items.length} Routes
                            </span>
                            <span className="px-2 py-1 rounded text-xs font-medium bg-slate-700 text-slate-300">
                                Total Time: {selectedBus.items[0].start_time} - {selectedBus.items[selectedBus.items.length - 1].end_time}
                            </span>
                        </div>
                    </div>

                    <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-6">
                        {selectedBus.items.map((item, idx) => (
                            <div key={idx} className="relative pl-6 border-l-2 border-slate-700 last:border-transparent">
                                {/* Timeline Dot */}
                                <div className={`absolute -left-[9px] top-0 h-4 w-4 rounded-full border-2 border-slate-900 ${item.type === 'entry' ? 'bg-emerald-500' : 'bg-amber-500'
                                    }`}></div>

                                <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50 hover:border-slate-600 transition-colors">
                                    <div className="flex justify-between items-start mb-3">
                                        <div className="flex flex-col">
                                            {/* Time Display with Strikethrough */}
                                            {item.time_shift_minutes !== 0 ? (
                                                <>
                                                    <span className="text-xs text-slate-500 line-through decoration-slate-500/50">
                                                        {item.original_start_time}
                                                    </span>
                                                    <span className="font-mono text-lg font-bold text-amber-400">
                                                        {item.start_time}
                                                    </span>
                                                </>
                                            ) : (
                                                <span className="font-mono text-lg font-bold text-white">
                                                    {item.start_time}
                                                </span>
                                            )}
                                        </div>

                                        <span className={`text-[10px] font-bold px-2 py-1 rounded uppercase tracking-wider ${item.type === 'entry' ? 'text-emerald-400 bg-emerald-400/10' : 'text-amber-400 bg-amber-400/10'
                                            }`}>
                                            {item.type}
                                        </span>
                                    </div>

                                    <div className="mb-3">
                                        <p className="text-sm text-slate-300 font-medium">Route {item.route_id}</p>
                                        <p className="text-xs text-slate-500 mt-1">Duration: {item.end_time} (Arrival)</p>
                                    </div>

                                    {/* Time Shift Alert */}
                                    {item.time_shift_minutes !== 0 && item.time_shift_minutes !== undefined && (
                                        <div className="flex items-start gap-2 text-xs bg-amber-500/10 border border-amber-500/20 rounded-lg p-2 text-amber-200">
                                            <svg className="w-4 h-4 flex-none mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                                            </svg>
                                            <div>
                                                <span className="font-bold">Schedule Adjusted</span>
                                                <p className="opacity-80 mt-0.5">
                                                    Shifted {item.time_shift_minutes > 0 ? '+' : ''}{item.time_shift_minutes} min to accommodate previous route.
                                                </p>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default MapView;
