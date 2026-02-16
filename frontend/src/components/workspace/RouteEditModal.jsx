/**
 * RouteEditModal - Modal para crear/editar rutas
 * 
 * Permite:
 * - Crear nuevas rutas desde cero
 * - Editar rutas existentes (horas, paradas, etc)
 * - Duplicar/ampliar rutas existentes
 */

import React, { useState, useEffect } from 'react';
import { X, Plus, Trash2, Clock, MapPin, Bus, Save, Copy, AlertCircle } from 'lucide-react';

const ROUTE_TYPES = [
  { value: 'entry', label: 'Entrada', color: 'bg-blue-500' },
  { value: 'exit', label: 'Salida', color: 'bg-amber-500' },
];

function formatTimeInput(timeValue) {
  if (!timeValue) return '';
  // Handle "HH:MM:SS" or "HH:MM" format
  const parts = String(timeValue).split(':');
  if (parts.length >= 2) {
    return `${parts[0].padStart(2, '0')}:${parts[1].padStart(2, '0')}`;
  }
  return timeValue;
}

function parseDuration(durationStr) {
  if (!durationStr) return 0;
  // Parse "980 min" or just "980"
  const match = String(durationStr).match(/(\d+)/);
  return match ? parseInt(match[1], 10) : 0;
}

function toInputNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? String(parsed) : '';
}

// Convert minutes from start to HH:MM time
function minutesToTime(minutes, baseTime) {
  if (!baseTime) return '';
  const [baseH, baseM] = baseTime.split(':').map(Number);
  const totalMinutes = baseH * 60 + baseM + minutes;
  const h = Math.floor(totalMinutes / 60) % 24;
  const m = totalMinutes % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

// Calculate minutes between two times
function timeDiffInMinutes(time1, time2) {
  if (!time1 || !time2) return 0;
  const [h1, m1] = time1.split(':').map(Number);
  const [h2, m2] = time2.split(':').map(Number);
  return (h2 * 60 + m2) - (h1 * 60 + m1);
}

export function RouteEditModal({ 
  isOpen, 
  onClose, 
  route = null, 
  onSave,
  mode = 'edit' // 'edit', 'create', 'duplicate'
}) {
  const [formData, setFormData] = useState({
    id: '',
    code: '',
    startTime: '',
    endTime: '',
    origin: '',
    destination: '',
    type: 'entry',
    stops: [],
    school: '',
    capacityNeeded: '',
    vehicleCapacityMin: '',
    vehicleCapacityMax: '',
    vehicleCapacityRange: '',
    contractId: '',
    startLat: '',
    startLon: '',
    endLat: '',
    endLon: '',
  });

  const [errors, setErrors] = useState({});

  // Initialize form when route changes
  useEffect(() => {
    if (route) {
      const startLocation =
        route.start_location ||
        route.start_loc ||
        route.rawRoute?.start_location ||
        route.rawRoute?.start_loc ||
        null;
      const endLocation =
        route.end_location ||
        route.end_loc ||
        route.rawRoute?.end_location ||
        route.rawRoute?.end_loc ||
        null;

      setFormData({
        id: route.id || '',
        code: route.code || route.id || '',
        startTime: formatTimeInput(route.startTime || route.departure_time),
        endTime: formatTimeInput(route.endTime || route.arrival_time),
        origin: route.origin || '',
        destination: route.destination || '',
        type: route.type || 'entry',
        stops: route.stops
          ? route.stops.map((stop, index) => ({
            id: stop.id || `stop_${Date.now()}_${index}`,
            name: stop.name || '',
            lat: toInputNumber(stop.lat ?? stop.latitude),
            lon: toInputNumber(stop.lon ?? stop.lng ?? stop.longitude),
            time_from_start: Number.isFinite(Number(stop.time_from_start)) ? Number(stop.time_from_start) : 0,
            passengers: Number.isFinite(Number(stop.passengers)) ? Number(stop.passengers) : 0,
            is_school: !!stop.is_school,
            order: Number.isFinite(Number(stop.order)) ? Number(stop.order) : (index + 1),
          }))
          : [],
        school: route.school || '',
        capacityNeeded: toInputNumber(
          route.capacityNeeded ??
          route.capacity_needed ??
          route.rawRoute?.capacity_needed
        ),
        vehicleCapacityMin: toInputNumber(
          route.vehicle_capacity_min ??
          route.vehicleCapacityMin ??
          route.rawRoute?.vehicle_capacity_min
        ),
        vehicleCapacityMax: toInputNumber(
          route.vehicle_capacity_max ??
          route.vehicleCapacityMax ??
          route.rawRoute?.vehicle_capacity_max
        ),
        vehicleCapacityRange: String(
          route.vehicle_capacity_range ??
          route.vehicleCapacityRange ??
          route.rawRoute?.vehicle_capacity_range ??
          ''
        ),
        contractId: String(route.contract_id ?? route.contractId ?? route.rawRoute?.contract_id ?? ''),
        startLat: Array.isArray(startLocation) && startLocation.length === 2 ? toInputNumber(startLocation[0]) : '',
        startLon: Array.isArray(startLocation) && startLocation.length === 2 ? toInputNumber(startLocation[1]) : '',
        endLat: Array.isArray(endLocation) && endLocation.length === 2 ? toInputNumber(endLocation[0]) : '',
        endLon: Array.isArray(endLocation) && endLocation.length === 2 ? toInputNumber(endLocation[1]) : '',
      });
    } else if (mode === 'create') {
      setFormData({
        id: `ROUTE_${Date.now()}`,
        code: '',
        startTime: '08:00',
        endTime: '08:30',
        origin: '',
        destination: '',
        type: 'entry',
        stops: [],
        school: '',
        capacityNeeded: '',
        vehicleCapacityMin: '',
        vehicleCapacityMax: '',
        vehicleCapacityRange: '',
        contractId: '',
        startLat: '',
        startLon: '',
        endLat: '',
        endLon: '',
      });
    }
    setErrors({});
  }, [route, mode, isOpen]);

  const validate = () => {
    const newErrors = {};
    
    if (!formData.code.trim()) {
      newErrors.code = 'El código es obligatorio';
    }
    
    if (!formData.startTime) {
      newErrors.startTime = 'Hora de inicio obligatoria';
    }
    
    if (!formData.endTime) {
      newErrors.endTime = 'Hora de fin obligatoria';
    }
    
    if (formData.startTime && formData.endTime) {
      const [startH, startM] = formData.startTime.split(':').map(Number);
      const [endH, endM] = formData.endTime.split(':').map(Number);
      const startMinutes = startH * 60 + startM;
      const endMinutes = endH * 60 + endM;
      
      if (endMinutes <= startMinutes) {
        newErrors.endTime = 'La hora de fin debe ser posterior a la de inicio';
      }
    }
    
    if (!formData.origin.trim()) {
      newErrors.origin = 'El origen es obligatorio';
    }
    
    if (!formData.destination.trim()) {
      newErrors.destination = 'El destino es obligatorio';
    }

    const capacityNeeded = Number(formData.capacityNeeded);
    if (formData.capacityNeeded !== '' && (!Number.isFinite(capacityNeeded) || capacityNeeded < 0)) {
      newErrors.capacityNeeded = 'Las plazas requeridas deben ser un numero mayor o igual a 0';
    }

    const vehicleCapacityMin = Number(formData.vehicleCapacityMin);
    if (formData.vehicleCapacityMin !== '' && (!Number.isFinite(vehicleCapacityMin) || vehicleCapacityMin < 0)) {
      newErrors.vehicleCapacityMin = 'La capacidad minima debe ser un numero mayor o igual a 0';
    }

    const vehicleCapacityMax = Number(formData.vehicleCapacityMax);
    if (formData.vehicleCapacityMax !== '' && (!Number.isFinite(vehicleCapacityMax) || vehicleCapacityMax < 0)) {
      newErrors.vehicleCapacityMax = 'La capacidad maxima debe ser un numero mayor o igual a 0';
    }

    if (
      formData.vehicleCapacityMin !== '' &&
      formData.vehicleCapacityMax !== '' &&
      Number.isFinite(vehicleCapacityMin) &&
      Number.isFinite(vehicleCapacityMax) &&
      vehicleCapacityMin > vehicleCapacityMax
    ) {
      newErrors.vehicleCapacityMax = 'La capacidad maxima debe ser mayor o igual que la minima';
    }

    const hasStartCoord = formData.startLat !== '' || formData.startLon !== '';
    if (hasStartCoord) {
      const startLat = Number(formData.startLat);
      const startLon = Number(formData.startLon);
      if (!Number.isFinite(startLat) || !Number.isFinite(startLon)) {
        newErrors.startCoords = 'Coordenadas de inicio invalidas';
      } else if (Math.abs(startLat) > 90 || Math.abs(startLon) > 180) {
        newErrors.startCoords = 'Coordenadas de inicio fuera de rango';
      }
    }

    const hasEndCoord = formData.endLat !== '' || formData.endLon !== '';
    if (hasEndCoord) {
      const endLat = Number(formData.endLat);
      const endLon = Number(formData.endLon);
      if (!Number.isFinite(endLat) || !Number.isFinite(endLon)) {
        newErrors.endCoords = 'Coordenadas de destino invalidas';
      } else if (Math.abs(endLat) > 90 || Math.abs(endLon) > 180) {
        newErrors.endCoords = 'Coordenadas de destino fuera de rango';
      }
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = () => {
    if (!validate()) return;

    const parseCoordPair = (latValue, lonValue) => {
      const lat = Number(latValue);
      const lon = Number(lonValue);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
      return [lat, lon];
    };

    const normalizedStops = (formData.stops || []).map((stop, index) => ({
      id: stop.id || `stop_${Date.now()}_${index}`,
      name: stop.name || '',
      lat: Number.isFinite(Number(stop.lat)) ? Number(stop.lat) : 0,
      lon: Number.isFinite(Number(stop.lon)) ? Number(stop.lon) : 0,
      time_from_start: Number.isFinite(Number(stop.time_from_start)) ? Number(stop.time_from_start) : 0,
      passengers: Number.isFinite(Number(stop.passengers)) ? Number(stop.passengers) : 0,
      is_school: !!stop.is_school,
      order: index + 1,
    }));
    
    const savedRoute = {
      ...formData,
      // Ensure proper time format
      startTime: formData.startTime,
      endTime: formData.endTime,
      // Calculate duration
      duration: calculateDuration(formData.startTime, formData.endTime),
      capacityNeeded: Number.isFinite(Number(formData.capacityNeeded)) ? Number(formData.capacityNeeded) : 0,
      vehicle_capacity_min: Number.isFinite(Number(formData.vehicleCapacityMin)) ? Number(formData.vehicleCapacityMin) : null,
      vehicle_capacity_max: Number.isFinite(Number(formData.vehicleCapacityMax)) ? Number(formData.vehicleCapacityMax) : null,
      vehicle_capacity_range: formData.vehicleCapacityRange?.trim() || null,
      contract_id: formData.contractId?.trim() || null,
      start_location: parseCoordPair(formData.startLat, formData.startLon),
      end_location: parseCoordPair(formData.endLat, formData.endLon),
      stops: normalizedStops,
    };
    
    onSave(savedRoute);
    onClose();
  };

  const calculateDuration = (start, end) => {
    const [startH, startM] = start.split(':').map(Number);
    const [endH, endM] = end.split(':').map(Number);
    return (endH * 60 + endM) - (startH * 60 + startM);
  };

  const addStop = () => {
    setFormData(prev => ({
      ...prev,
      stops: [...prev.stops, { 
        id: `stop_${Date.now()}`,
        name: '', 
        lat: '', 
        lon: '', 
        time_from_start: 0,
        passengers: 0,
        is_school: false,
        order: prev.stops.length + 1 
      }]
    }));
  };

  const removeStop = (index) => {
    setFormData(prev => ({
      ...prev,
      stops: prev.stops.filter((_, i) => i !== index)
    }));
  };

  const updateStop = (index, field, value) => {
    setFormData(prev => ({
      ...prev,
      stops: prev.stops.map((stop, i) => 
        i === index ? { ...stop, [field]: value } : stop
      )
    }));
  };

  if (!isOpen) return null;

  const title = mode === 'create' ? 'Nueva Ruta' : mode === 'duplicate' ? 'Duplicar Ruta' : 'Editar Ruta';

  return (
    <div 
      className="fixed inset-0 flex items-center justify-center bg-black/70 backdrop-blur-sm"
      style={{ zIndex: 99999 }}
    >
      <div 
        className="bg-[#1c1c1f] border border-gray-700 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden shadow-2xl relative"
        style={{ zIndex: 100000 }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700 bg-gray-900/50">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${formData.type === 'entry' ? 'bg-blue-500/20' : 'bg-amber-500/20'}`}>
              <Bus className={`w-5 h-5 ${formData.type === 'entry' ? 'text-blue-400' : 'text-amber-400'}`} />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">{title}</h2>
              <p className="text-xs text-gray-400">
                {mode === 'create' ? 'Crear una ruta nueva' : mode === 'duplicate' ? 'Crear copia de ruta existente' : 'Modificar ruta existente'}
              </p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-140px)]">
          <div className="space-y-6">
            {/* Basic Info */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">
                  Código de Ruta *
                </label>
                <input
                  type="text"
                  value={formData.code}
                  onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500"
                  placeholder="Ej: UE361701"
                />
                {errors.code && <p className="text-xs text-red-400 mt-1">{errors.code}</p>}
                <p className="text-[10px] text-gray-500 mt-1 data-mono">ID interno: {formData.id || '-'}</p>
              </div>
              
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">
                  Tipo
                </label>
                <div className="flex gap-2">
                  {ROUTE_TYPES.map(type => (
                    <button
                      key={type.value}
                      onClick={() => setFormData({ ...formData, type: type.value })}
                      className={`flex-1 py-2 px-3 rounded-lg text-xs font-medium transition-all ${
                        formData.type === type.value
                          ? `${type.color} text-white`
                          : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                      }`}
                    >
                      {type.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Times */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {formData.type === 'entry' ? 'Hora Salida Origen' : 'Hora Salida Colegio'} *
                  </span>
                </label>
                <input
                  type="time"
                  value={formData.startTime}
                  onChange={(e) => setFormData({ ...formData, startTime: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500"
                />
                {errors.startTime && <p className="text-xs text-red-400 mt-1">{errors.startTime}</p>}
              </div>
              
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {formData.type === 'entry' ? 'Hora Llegada Colegio' : 'Hora Llegada Destino'} *
                  </span>
                </label>
                <input
                  type="time"
                  value={formData.endTime}
                  onChange={(e) => setFormData({ ...formData, endTime: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500"
                />
                {errors.endTime && <p className="text-xs text-red-400 mt-1">{errors.endTime}</p>}
              </div>
            </div>

            {/* Duration display */}
            {formData.startTime && formData.endTime && !errors.endTime && (
              <div className="flex items-center gap-2 text-xs text-gray-400 bg-gray-800/50 p-2 rounded-lg">
                <Clock className="w-3 h-3" />
                Duración: <span className="text-white font-medium">{calculateDuration(formData.startTime, formData.endTime)} minutos</span>
              </div>
            )}

            {/* Locations */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">
                  <span className="flex items-center gap-1">
                    <MapPin className="w-3 h-3" />
                    Origen *
                  </span>
                </label>
                <input
                  type="text"
                  value={formData.origin}
                  onChange={(e) => setFormData({ ...formData, origin: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500"
                  placeholder="Punto de origen"
                />
                {errors.origin && <p className="text-xs text-red-400 mt-1">{errors.origin}</p>}
              </div>
              
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">
                  <span className="flex items-center gap-1">
                    <MapPin className="w-3 h-3" />
                    Destino *
                  </span>
                </label>
                <input
                  type="text"
                  value={formData.destination}
                  onChange={(e) => setFormData({ ...formData, destination: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500"
                  placeholder="Punto de destino"
                />
                {errors.destination && <p className="text-xs text-red-400 mt-1">{errors.destination}</p>}
              </div>
            </div>

            {/* School */}
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">
                Colegio / Centro
              </label>
              <input
                type="text"
                value={formData.school}
                onChange={(e) => setFormData({ ...formData, school: e.target.value })}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500"
                placeholder="Nombre del colegio"
              />
            </div>

            {/* Route operating data */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">
                  Plazas requeridas (max alumnos)
                </label>
                <input
                  type="number"
                  min="0"
                  value={formData.capacityNeeded}
                  onChange={(e) => setFormData({ ...formData, capacityNeeded: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500"
                  placeholder="Ej: 28"
                />
                {errors.capacityNeeded && <p className="text-xs text-red-400 mt-1">{errors.capacityNeeded}</p>}
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">
                  Rango plazas vehiculo
                </label>
                <input
                  type="text"
                  value={formData.vehicleCapacityRange}
                  onChange={(e) => setFormData({ ...formData, vehicleCapacityRange: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500"
                  placeholder="Ej: 26-38"
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">
                  Min plazas vehiculo
                </label>
                <input
                  type="number"
                  min="0"
                  value={formData.vehicleCapacityMin}
                  onChange={(e) => setFormData({ ...formData, vehicleCapacityMin: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500"
                />
                {errors.vehicleCapacityMin && <p className="text-xs text-red-400 mt-1">{errors.vehicleCapacityMin}</p>}
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">
                  Max plazas vehiculo
                </label>
                <input
                  type="number"
                  min="0"
                  value={formData.vehicleCapacityMax}
                  onChange={(e) => setFormData({ ...formData, vehicleCapacityMax: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500"
                />
                {errors.vehicleCapacityMax && <p className="text-xs text-red-400 mt-1">{errors.vehicleCapacityMax}</p>}
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">
                  Contrato
                </label>
                <input
                  type="text"
                  value={formData.contractId}
                  onChange={(e) => setFormData({ ...formData, contractId: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500"
                  placeholder="UE3617"
                />
              </div>
            </div>

            {/* Coordinates */}
            <div className="border-t border-gray-700 pt-4">
              <h3 className="text-sm font-medium text-white mb-3">Coordenadas operativas</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <div className="text-xs font-medium text-gray-400 uppercase tracking-wide">Inicio</div>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="number"
                      step="0.000001"
                      value={formData.startLat}
                      onChange={(e) => setFormData({ ...formData, startLat: e.target.value })}
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500"
                      placeholder="Lat"
                    />
                    <input
                      type="number"
                      step="0.000001"
                      value={formData.startLon}
                      onChange={(e) => setFormData({ ...formData, startLon: e.target.value })}
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500"
                      placeholder="Lon"
                    />
                  </div>
                  {errors.startCoords && <p className="text-xs text-red-400 mt-1">{errors.startCoords}</p>}
                </div>

                <div className="space-y-2">
                  <div className="text-xs font-medium text-gray-400 uppercase tracking-wide">Destino</div>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="number"
                      step="0.000001"
                      value={formData.endLat}
                      onChange={(e) => setFormData({ ...formData, endLat: e.target.value })}
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500"
                      placeholder="Lat"
                    />
                    <input
                      type="number"
                      step="0.000001"
                      value={formData.endLon}
                      onChange={(e) => setFormData({ ...formData, endLon: e.target.value })}
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500"
                      placeholder="Lon"
                    />
                  </div>
                  {errors.endCoords && <p className="text-xs text-red-400 mt-1">{errors.endCoords}</p>}
                </div>
              </div>
            </div>

            {/* Stops Section */}
            <div className="border-t border-gray-700 pt-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-sm font-medium text-white">Paradas</h3>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Hora de paso por cada parada (basada en hora inicio: {formData.startTime || '--:--'})
                  </p>
                </div>
                <button
                  onClick={addStop}
                  className="flex items-center gap-1 px-3 py-1.5 bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-400 rounded-lg text-xs transition-colors"
                >
                  <Plus className="w-3 h-3" />
                  Añadir Parada
                </button>
              </div>

              <div className="space-y-2">
                {formData.stops.map((stop, index) => {
                  // Calculate display time from time_from_start
                  const displayTime = formData.startTime 
                    ? minutesToTime(stop.time_from_start || 0, formData.startTime)
                    : '';
                  
                  return (
                    <div key={stop.id || index} className="p-3 bg-gray-800/50 rounded-lg space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500 w-6">{index + 1}</span>
                        <input
                          type="text"
                          value={stop.name}
                          onChange={(e) => updateStop(index, 'name', e.target.value)}
                          className="flex-1 px-2 py-1.5 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:border-indigo-500"
                          placeholder="Nombre de parada"
                        />
                        <div className="flex items-center gap-1">
                          <Clock className="w-3 h-3 text-gray-500" />
                          <input
                            type="time"
                            value={displayTime}
                            onChange={(e) => {
                              const newTime = e.target.value;
                              if (formData.startTime) {
                                const minutesDiff = timeDiffInMinutes(formData.startTime, newTime);
                                updateStop(index, 'time_from_start', Math.max(0, minutesDiff));
                              }
                            }}
                            className="w-24 px-2 py-1.5 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:border-indigo-500"
                          />
                        </div>
                        <button
                          onClick={() => removeStop(index)}
                          className="p-1.5 hover:bg-red-500/20 text-gray-400 hover:text-red-400 rounded transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>

                      <div className="grid grid-cols-4 gap-2">
                        <input
                          type="number"
                          step="0.000001"
                          value={stop.lat}
                          onChange={(e) => updateStop(index, 'lat', e.target.value)}
                          className="px-2 py-1.5 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:border-indigo-500"
                          placeholder="Lat"
                        />
                        <input
                          type="number"
                          step="0.000001"
                          value={stop.lon}
                          onChange={(e) => updateStop(index, 'lon', e.target.value)}
                          className="px-2 py-1.5 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:border-indigo-500"
                          placeholder="Lon"
                        />
                        <input
                          type="number"
                          min="0"
                          value={stop.passengers ?? 0}
                          onChange={(e) => updateStop(index, 'passengers', Number(e.target.value || 0))}
                          className="px-2 py-1.5 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:border-indigo-500"
                          placeholder="Alumnos"
                        />
                        <label className="flex items-center gap-1 px-2 py-1.5 bg-gray-700 border border-gray-600 rounded text-[11px] text-gray-300">
                          <input
                            type="checkbox"
                            checked={!!stop.is_school}
                            onChange={(e) => updateStop(index, 'is_school', e.target.checked)}
                            className="accent-indigo-500"
                          />
                          Colegio
                        </label>
                      </div>
                    </div>
                  );
                })}
                
                {formData.stops.length === 0 && (
                  <div className="text-center py-6">
                    <AlertCircle className="w-8 h-8 text-gray-600 mx-auto mb-2" />
                    <p className="text-xs text-gray-500">
                      Sin paradas. Haz clic en "Añadir Parada" para agregar.
                    </p>
                  </div>
                )}
              </div>
              
              {/* Info about first stop */}
              {formData.stops.length > 0 && (
                <div className="mt-3 p-2 bg-gray-800/30 rounded-lg">
                  <p className="text-[10px] text-gray-500">
                    💡 La primera parada marca el inicio de la ruta. Las horas se calculan desde la hora de salida.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-700 bg-gray-900/50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-400 hover:text-white text-sm transition-colors"
          >
            Cancelar
          </button>
          <button
            onClick={handleSubmit}
            className="flex items-center gap-2 px-6 py-2 bg-indigo-500 hover:bg-indigo-600 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <Save className="w-4 h-4" />
            {mode === 'create' ? 'Crear Ruta' : 'Guardar Cambios'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default RouteEditModal;
