/**
 * RouteEditorDrawer - Drawer lateral de edición de ruta
 * 
 * Se abre al hacer clic en una ruta desde el timeline.
 * Permite editar todos los datos de la ruta de forma intuitiva.
 * 
 * @module components/timeline-editable/RouteEditorDrawer
 * @version 1.0.0
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useTimelineEditableStore } from '../../stores/timelineEditableStore';
import { StopEditor } from './StopEditor';
import {
  X,
  Lock,
  Unlock,
  Clock,
  MapPin,
  Bus,
  School,
  AlertCircle,
  Save,
  ArrowRight,
  ArrowLeft,
  Info,
  GripVertical,
  Plus,
  Trash2,
  AlertTriangle
} from 'lucide-react';

/**
 * Drawer de edición de ruta con slide-in desde la derecha
 * 
 * @param {Object} props
 * @param {Object} props.route - Ruta a editar
 * @param {boolean} props.isOpen - Estado de apertura del drawer
 * @param {Function} props.onClose - Callback al cerrar
 * @param {Function} props.onSave - Callback al guardar (opcional)
 */
export function RouteEditorDrawer({ route, isOpen, onClose, onSave }) {
  const {
    toggleRouteLock,
    updateRoute,
    moveRoute,
    buses,
    validateRoute,
    calculateCompatibility
  } = useTimelineEditableStore();

  // Estado local para edición
  const [editedRoute, setEditedRoute] = useState(null);
  const [hasChanges, setHasChanges] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [validationErrors, setValidationErrors] = useState([]);
  const [showUnsavedConfirm, setShowUnsavedConfirm] = useState(false);

  // Inicializar cuando se abre
  useEffect(() => {
    if (route && isOpen) {
      setEditedRoute({
        ...route,
        stops: route.stops ? [...route.stops.map((s, i) => ({ ...s, tempId: s.stop_id || `stop-${i}` }))] : []
      });
      setHasChanges(false);
      setValidationErrors([]);
    }
  }, [route, isOpen]);

  // Cerrar con Escape
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen) {
        handleClose();
      }
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isOpen, hasChanges]);

  // Bloquear scroll del body cuando está abierto
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  const handleClose = useCallback(() => {
    if (hasChanges) {
      setShowUnsavedConfirm(true);
    } else {
      onClose();
    }
  }, [hasChanges, onClose]);

  const confirmClose = useCallback(() => {
    setShowUnsavedConfirm(false);
    onClose();
  }, [onClose]);

  const handleLockToggle = useCallback(() => {
    if (editedRoute) {
      toggleRouteLock(editedRoute.route_id);
      setEditedRoute(prev => ({ ...prev, isLocked: !prev.isLocked }));
      setHasChanges(true);
    }
  }, [editedRoute, toggleRouteLock]);

  // Calcular duración entre dos tiempos
  const calculateDuration = useCallback((startTime, endTime) => {
    if (!startTime || !endTime) return 0;
    const [startH, startM] = startTime.split(':').map(Number);
    const [endH, endM] = endTime.split(':').map(Number);
    const startMinutes = startH * 60 + startM;
    const endMinutes = endH * 60 + endM;
    return endMinutes - startMinutes;
  }, []);

  // Validar solapamientos
  const checkOverlaps = useCallback((updates) => {
    const errors = [];
    const currentBus = buses.find(b => b.busId === (updates.assignedBusId || editedRoute?.assignedBusId));
    
    if (!currentBus) return errors;

    const startTime = updates.currentStartTime || editedRoute?.currentStartTime;
    const endTime = updates.currentEndTime || editedRoute?.currentEndTime;
    
    if (!startTime || !endTime) return errors;

    const routeStart = startTime.split(':').map(Number);
    const routeEnd = endTime.split(':').map(Number);
    const startMinutes = routeStart[0] * 60 + routeStart[1];
    const endMinutes = routeEnd[0] * 60 + routeEnd[1];

    currentBus.routes.forEach(otherRoute => {
      if (otherRoute.route_id === editedRoute?.route_id) return;
      
      const otherStart = (otherRoute.currentStartTime || otherRoute.start_time).split(':').map(Number);
      const otherEnd = (otherRoute.currentEndTime || otherRoute.end_time).split(':').map(Number);
      const otherStartMinutes = otherStart[0] * 60 + otherStart[1];
      const otherEndMinutes = otherEnd[0] * 60 + otherEnd[1];

      if (startMinutes < otherEndMinutes && endMinutes > otherStartMinutes) {
        errors.push({
          type: 'overlap',
          message: `Se solapa con ${otherRoute.route_code} (${otherRoute.currentStartTime || otherRoute.start_time} - ${otherRoute.currentEndTime || otherRoute.end_time})`
        });
      }
    });

    return errors;
  }, [buses, editedRoute]);

  const handleBusChange = useCallback((busId) => {
    setEditedRoute(prev => {
      const updates = { ...prev, assignedBusId: busId || null };
      const overlaps = checkOverlaps(updates);
      setValidationErrors(overlaps);
      return updates;
    });
    setHasChanges(true);
  }, [checkOverlaps]);

  const handleTimeChange = useCallback((field, value) => {
    setEditedRoute(prev => {
      const updated = { ...prev, [field]: value };
      
      // Recalcular hora de fin si cambia la de inicio
      if (field === 'currentStartTime' && prev.duration_minutes) {
        const [h, m] = value.split(':').map(Number);
        const startMinutes = h * 60 + m;
        const endMinutes = startMinutes + prev.duration_minutes;
        const endH = Math.floor(endMinutes / 60);
        const endM = endMinutes % 60;
        updated.currentEndTime = `${endH.toString().padStart(2, '0')}:${endM.toString().padStart(2, '0')}`;
      }
      
      // Validar solapamientos
      const overlaps = checkOverlaps(updated);
      setValidationErrors(overlaps);
      
      return updated;
    });
    setHasChanges(true);
  }, [checkOverlaps]);

  const handleStopsReorder = useCallback((reorderedStops) => {
    setEditedRoute(prev => ({ ...prev, stops: reorderedStops }));
    setHasChanges(true);
  }, []);

  const handleStopUpdate = useCallback((stopId, updates) => {
    setEditedRoute(prev => ({
      ...prev,
      stops: prev.stops.map(stop =>
        stop.tempId === stopId ? { ...stop, ...updates } : stop
      )
    }));
    setHasChanges(true);
  }, []);

  const handleAddStop = useCallback(() => {
    setEditedRoute(prev => ({
      ...prev,
      stops: [
        ...prev.stops,
        {
          tempId: `new-stop-${Date.now()}`,
          stop_name: 'Nueva parada',
          latitude: 0,
          longitude: 0,
          time_from_start: 0,
          is_school: false
        }
      ]
    }));
    setHasChanges(true);
  }, []);

  const handleRemoveStop = useCallback((stopId) => {
    setEditedRoute(prev => ({
      ...prev,
      stops: prev.stops.filter(stop => stop.tempId !== stopId)
    }));
    setHasChanges(true);
  }, []);

  const handleSave = useCallback(async () => {
    if (!editedRoute || editedRoute.isLocked || validationErrors.length > 0) return;

    setIsSaving(true);

    // Simular delay para feedback visual
    await new Promise(resolve => setTimeout(resolve, 300));

    // Actualizar en el store
    updateRoute(editedRoute.route_id, {
      currentStartTime: editedRoute.currentStartTime,
      currentEndTime: editedRoute.currentEndTime,
      stops: editedRoute.stops.map(({ tempId, ...stop }) => stop)
    });

    // Mover a otro bus si cambió
    if (editedRoute.assignedBusId !== route?.assignedBusId) {
      moveRoute(editedRoute.route_id, editedRoute.assignedBusId || null);
    }

    setHasChanges(false);
    setIsSaving(false);
    onSave?.(editedRoute);
    onClose();
  }, [editedRoute, route, validationErrors, updateRoute, moveRoute, onSave, onClose]);

  // Duración calculada
  const calculatedDuration = useMemo(() => {
    if (!editedRoute) return 0;
    return calculateDuration(
      editedRoute.currentStartTime || editedRoute.start_time,
      editedRoute.currentEndTime || editedRoute.end_time
    );
  }, [editedRoute, calculateDuration]);

  if (!isOpen || !editedRoute) return null;

  const isEntry = editedRoute.type === 'entry';
  const typeColor = isEntry ? 'blue' : 'amber';
  const typeColors = {
    blue: { bg: 'bg-blue-500', text: 'text-blue-400', border: 'border-blue-500/30', light: 'bg-blue-500/10' },
    amber: { bg: 'bg-amber-500', text: 'text-amber-400', border: 'border-amber-500/30', light: 'bg-amber-500/10' }
  };

  return (
    <>
      {/* Overlay oscuro */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 transition-opacity duration-300"
        onClick={handleClose}
      />

      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-[400px] bg-[#13131a] border-l border-gray-800 z-50 shadow-2xl transform transition-transform duration-300 ease-out animate-in slide-in-from-right">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-800">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${typeColors[typeColor].light} ${typeColors[typeColor].text}`}>
              {isEntry ? <ArrowRight className="w-5 h-5" /> : <ArrowLeft className="w-5 h-5" />}
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Editar Ruta</h2>
              <p className="text-gray-500 text-xs">{editedRoute.route_code}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {hasChanges && (
              <span className="bg-amber-500/20 text-amber-400 text-xs px-2 py-1 rounded-full flex items-center gap-1">
                <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                Sin guardar
              </span>
            )}
            <button
              onClick={handleClose}
              className="p-2 hover:bg-gray-800 rounded-lg text-gray-400 hover:text-white transition-colors"
              title="Cerrar (Esc)"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6" style={{ height: 'calc(100vh - 180px)' }}>
          {/* Toggle Bloqueada */}
          <section className="bg-gray-900/50 rounded-xl p-4 border border-gray-800">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${editedRoute.isLocked ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'}`}>
                  {editedRoute.isLocked ? <Lock className="w-4 h-4" /> : <Unlock className="w-4 h-4" />}
                </div>
                <div>
                  <span className="text-white font-medium">
                    {editedRoute.isLocked ? 'Bloqueada' : 'Editable'}
                  </span>
                  <p className="text-gray-500 text-xs">
                    {editedRoute.isLocked ? 'La ruta no se puede modificar' : 'Puedes editar esta ruta'}
                  </p>
                </div>
              </div>
              <button
                onClick={handleLockToggle}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  editedRoute.isLocked ? 'bg-red-500' : 'bg-green-500'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    editedRoute.isLocked ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          </section>

          {/* Información del Colegio (Solo lectura) */}
          <section>
            <label className="text-gray-400 text-xs uppercase tracking-wider font-medium mb-3 flex items-center gap-2">
              <School className="w-3.5 h-3.5" />
              Colegio
            </label>
            <div className="bg-gray-900/50 rounded-lg p-3 border border-gray-800">
              <div className="text-white font-medium">{editedRoute.school || editedRoute.route_name || 'Sin nombre'}</div>
              <div className="text-gray-500 text-xs mt-1 flex items-center gap-2">
                <MapPin className="w-3 h-3" />
                {editedRoute.startCoordinates?.lat?.toFixed(6) || 0}, {editedRoute.startCoordinates?.lon?.toFixed(6) || 0}
              </div>
            </div>
          </section>

          {/* Bus Asignado */}
          <section>
            <label className="text-gray-400 text-xs uppercase tracking-wider font-medium mb-3 flex items-center gap-2">
              <Bus className="w-3.5 h-3.5" />
              Asignada a
            </label>
            <select
              value={editedRoute.assignedBusId || ''}
              onChange={(e) => handleBusChange(e.target.value || null)}
              disabled={editedRoute.isLocked}
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2.5 text-white focus:border-indigo-500 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <option value="">Sin asignar</option>
              {buses.map(bus => (
                <option key={bus.busId} value={bus.busId}>
                  {bus.busName} ({bus.routes.length} rutas)
                </option>
              ))}
            </select>
          </section>

          {/* Horarios */}
          <section>
            <label className="text-gray-400 text-xs uppercase tracking-wider font-medium mb-3 flex items-center gap-2">
              <Clock className="w-3.5 h-3.5" />
              Horario
            </label>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-gray-500 text-xs mb-1.5 block">Inicio</label>
                  <input
                    type="time"
                    value={editedRoute.currentStartTime || editedRoute.start_time}
                    onChange={(e) => handleTimeChange('currentStartTime', e.target.value)}
                    disabled={editedRoute.isLocked}
                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white focus:border-indigo-500 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-mono"
                  />
                </div>
                <div>
                  <label className="text-gray-500 text-xs mb-1.5 block">Fin</label>
                  <input
                    type="time"
                    value={editedRoute.currentEndTime || editedRoute.end_time}
                    onChange={(e) => handleTimeChange('currentEndTime', e.target.value)}
                    disabled={editedRoute.isLocked}
                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white focus:border-indigo-500 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-mono"
                  />
                </div>
              </div>
              
              {/* Duración calculada */}
              <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-lg p-3 flex items-center justify-between">
                <span className="text-indigo-300 text-sm flex items-center gap-2">
                  <Clock className="w-4 h-4" />
                  Duración calculada
                </span>
                <span className="text-white font-mono font-medium">{calculatedDuration} min</span>
              </div>
            </div>
          </section>

          {/* Errores de validación */}
          {validationErrors.length > 0 && (
            <section className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-red-400 text-sm font-medium">Solapamiento detectado</p>
                  <ul className="text-red-400/80 text-xs mt-1 space-y-1">
                    {validationErrors.map((error, i) => (
                      <li key={i}>• {error.message}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </section>
          )}

          {/* Paradas */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <label className="text-gray-400 text-xs uppercase tracking-wider font-medium flex items-center gap-2">
                <MapPin className="w-3.5 h-3.5" />
                Paradas ({editedRoute.stops?.length || 0})
              </label>
              <span className="text-gray-500 text-xs">
                {editedRoute.isLocked ? 'Bloqueado' : 'Arrastra para ordenar'}
              </span>
            </div>
            
            <StopEditor
              stops={editedRoute.stops || []}
              isLocked={editedRoute.isLocked}
              onReorder={handleStopsReorder}
              onUpdate={handleStopUpdate}
              onRemove={handleRemoveStop}
            />
            
            {!editedRoute.isLocked && (
              <button
                onClick={handleAddStop}
                className="mt-3 w-full py-2.5 border border-dashed border-gray-700 hover:border-indigo-500/50 hover:bg-indigo-500/5 rounded-lg text-gray-400 hover:text-indigo-400 text-sm flex items-center justify-center gap-2 transition-colors"
              >
                <Plus className="w-4 h-4" />
                Añadir parada
              </button>
            )}
          </section>

          {/* Campos solo lectura adicionales */}
          <section className="border-t border-gray-800 pt-4">
            <label className="text-gray-500 text-xs uppercase tracking-wider font-medium mb-3 flex items-center gap-2">
              <Info className="w-3.5 h-3.5" />
              Información adicional
            </label>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between py-2 border-b border-gray-800/50">
                <span className="text-gray-500">ID de Ruta</span>
                <span className="text-gray-400 font-mono">{editedRoute.route_id}</span>
              </div>
              <div className="flex justify-between py-2 border-b border-gray-800/50">
                <span className="text-gray-500">Tipo</span>
                <span className={`${typeColors[typeColor].text} flex items-center gap-1`}>
                  {isEntry ? <ArrowRight className="w-3 h-3" /> : <ArrowLeft className="w-3 h-3" />}
                  {isEntry ? 'Entrada' : 'Salida'}
                </span>
              </div>
              <div className="flex justify-between py-2 border-b border-gray-800/50">
                <span className="text-gray-500">Duración original</span>
                <span className="text-gray-400">{editedRoute.duration_minutes} min</span>
              </div>
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-800 bg-[#13131a]">
          <div className="flex items-center justify-between gap-3">
            <button
              onClick={handleClose}
              className="px-4 py-2.5 text-gray-400 hover:text-white transition-colors text-sm"
            >
              Cancelar
            </button>
            <button
              onClick={handleSave}
              disabled={!hasChanges || editedRoute.isLocked || isSaving || validationErrors.length > 0}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-800 disabled:text-gray-500 text-white rounded-lg font-medium transition-colors"
            >
              {isSaving ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Guardando...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  Guardar cambios
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Confirmación de cambios sin guardar */}
      {showUnsavedConfirm && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="bg-[#1a1a23] border border-gray-700 rounded-xl p-6 max-w-sm mx-4 shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-amber-500/20 flex items-center justify-center">
                <AlertCircle className="w-5 h-5 text-amber-400" />
              </div>
              <h3 className="text-lg font-semibold text-white">Cambios sin guardar</h3>
            </div>
            <p className="text-gray-400 mb-6">
              Has realizado cambios que no han sido guardados. ¿Quieres descartarlos?
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowUnsavedConfirm(false)}
                className="flex-1 px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-700 transition-colors"
              >
                Seguir editando
              </button>
              <button
                onClick={confirmClose}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-500 transition-colors"
              >
                Descartar
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default RouteEditorDrawer;
