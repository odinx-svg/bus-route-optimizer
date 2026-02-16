/**
 * RouteEditModal - Modal completo para editar una ruta
 * 
 * Se abre al hacer clic en una ruta del timeline.
 * Permite ver y editar todos los datos de la ruta.
 * 
 * @module components/timeline-editable/RouteEditModal
 * @version 1.0.0
 */

import { useState, useEffect, useCallback } from 'react';
import { useTimelineEditableStore } from '../../stores/timelineEditableStore';
import { 
  X, 
  Lock, 
  Unlock, 
  Clock, 
  MapPin, 
  Bus, 
  School,
  Route,
  AlertCircle,
  Save,
  Trash2,
  GripVertical,
  ArrowRight,
  ArrowLeft,
  CheckCircle2
} from 'lucide-react';

export function RouteEditModal({ route, isOpen, onClose }) {
  const { 
    toggleRouteLock, 
    updateRoute,
    calculateCompatibility,
    removeRoute
  } = useTimelineEditableStore();

  // Estado local para edición
  const [editedRoute, setEditedRoute] = useState(null);
  const [activeTab, setActiveTab] = useState('general'); // 'general' | 'stops' | 'times'
  const [hasChanges, setHasChanges] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Inicializar cuando se abre
  useEffect(() => {
    if (route && isOpen) {
      setEditedRoute({ 
        ...route,
        stops: route.stops ? [...route.stops] : []
      });
      setHasChanges(false);
      setActiveTab('general');
      setShowDeleteConfirm(false);
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

  const handleClose = useCallback(() => {
    if (hasChanges) {
      if (window.confirm('Hay cambios sin guardar. ¿Cerrar sin guardar?')) {
        onClose();
      }
    } else {
      onClose();
    }
  }, [hasChanges, onClose]);

  const handleLockToggle = useCallback(() => {
    if (editedRoute) {
      toggleRouteLock(editedRoute.route_id);
      setEditedRoute(prev => ({ ...prev, isLocked: !prev.isLocked }));
    }
  }, [editedRoute, toggleRouteLock]);

  const handleSave = useCallback(async () => {
    if (!editedRoute || editedRoute.isLocked) return;
    
    setIsSaving(true);
    
    // Simular pequeño delay para feedback visual
    await new Promise(resolve => setTimeout(resolve, 300));
    
    updateRoute(editedRoute.route_id, {
      currentStartTime: editedRoute.currentStartTime,
      currentEndTime: editedRoute.currentEndTime,
      stops: editedRoute.stops
    });
    
    setHasChanges(false);
    setIsSaving(false);
    onClose();
  }, [editedRoute, updateRoute, onClose]);

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
      
      return updated;
    });
    setHasChanges(true);
  }, []);

  const handleDelete = useCallback(() => {
    if (editedRoute && !editedRoute.isLocked) {
      removeRoute(editedRoute.route_id);
      onClose();
    }
  }, [editedRoute, removeRoute, onClose]);

  if (!isOpen || !editedRoute) return null;

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => e.target === e.currentTarget && handleClose()}
    >
      <div className="w-full max-w-3xl max-h-[90vh] bg-[#13131a] rounded-2xl border border-gray-700 shadow-2xl flex flex-col animate-in fade-in zoom-in-95 duration-200">
        
        {/* Header */}
        <ModalHeader 
          route={editedRoute} 
          onClose={handleClose} 
          hasChanges={hasChanges}
        />

        {/* Tabs */}
        <div className="flex border-b border-gray-800">
          <TabButton 
            active={activeTab === 'general'} 
            onClick={() => setActiveTab('general')}
            icon={Route}
            label="General"
          />
          <TabButton 
            active={activeTab === 'times'} 
            onClick={() => setActiveTab('times')}
            icon={Clock}
            label="Horarios"
          />
          <TabButton 
            active={activeTab === 'stops'} 
            onClick={() => setActiveTab('stops')}
            icon={MapPin}
            label="Paradas"
          />
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'general' && (
            <GeneralTab 
              route={editedRoute} 
              onUpdate={setEditedRoute}
              setHasChanges={setHasChanges}
            />
          )}
          {activeTab === 'times' && (
            <TimesTab 
              route={editedRoute}
              onTimeChange={handleTimeChange}
            />
          )}
          {activeTab === 'stops' && (
            <StopsTab 
              route={editedRoute}
              onUpdate={setEditedRoute}
              setHasChanges={setHasChanges}
            />
          )}
        </div>

        {/* Footer */}
        <ModalFooter 
          route={editedRoute}
          onLockToggle={handleLockToggle}
          onSave={handleSave}
          onClose={handleClose}
          onDelete={() => setShowDeleteConfirm(true)}
          hasChanges={hasChanges}
          isSaving={isSaving}
        />

        {/* Confirmación de eliminación */}
        {showDeleteConfirm && (
          <DeleteConfirmDialog
            routeName={editedRoute.school || editedRoute.route_name}
            onConfirm={handleDelete}
            onCancel={() => setShowDeleteConfirm(false)}
          />
        )}
      </div>
    </div>
  );
}

// ============ SUB-COMPONENTES ============

function ModalHeader({ route, onClose, hasChanges }) {
  const isEntry = route.type === 'entry';
  
  return (
    <div className="flex items-center justify-between p-5 border-b border-gray-800">
      <div className="flex items-center gap-4">
        <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
          isEntry ? 'bg-blue-500/20 text-blue-400' : 'bg-amber-500/20 text-amber-400'
        }`}>
          {isEntry ? <ArrowRight className="w-6 h-6" /> : <ArrowLeft className="w-6 h-6" />}
        </div>
        <div>
          <h2 className="text-xl font-bold text-white">{route.school || route.route_name || 'Sin nombre'}</h2>
          <p className="text-gray-400 text-sm">{route.route_code}</p>
        </div>
        {hasChanges && (
          <span className="bg-amber-500/20 text-amber-400 text-xs px-2 py-1 rounded-full flex items-center gap-1">
            <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
            Cambios sin guardar
          </span>
        )}
        {route.isLocked && (
          <span className="bg-red-500/20 text-red-400 text-xs px-2 py-1 rounded-full flex items-center gap-1">
            <Lock className="w-3 h-3" />
            Bloqueada
          </span>
        )}
      </div>
      <button 
        onClick={onClose}
        className="p-2 hover:bg-gray-800 rounded-lg text-gray-400 hover:text-white transition-colors"
        title="Cerrar (Esc)"
      >
        <X className="w-5 h-5" />
      </button>
    </div>
  );
}

function TabButton({ active, onClick, icon: Icon, label }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
        active 
          ? 'text-white border-indigo-500' 
          : 'text-gray-400 border-transparent hover:text-gray-300 hover:border-gray-700'
      }`}
    >
      <Icon className="w-4 h-4" />
      {label}
    </button>
  );
}

function GeneralTab({ route, onUpdate, setHasChanges }) {
  const handleFieldChange = (field, value) => {
    onUpdate(prev => ({ ...prev, [field]: value }));
    setHasChanges(true);
  };

  return (
    <div className="space-y-6">
      {/* Información principal */}
      <section>
        <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
          <School className="w-4 h-4 text-indigo-400" />
          Información del Colegio
        </h3>
        <div className="grid grid-cols-2 gap-4">
          <Field 
            label="Nombre del colegio" 
            value={route.school || route.route_name || ''} 
            readOnly 
          />
          <Field 
            label="Código de Ruta" 
            value={route.route_code} 
            readOnly 
          />
          <Field 
            label="Tipo" 
            value={route.type === 'entry' ? 'Entrada' : 'Salida'} 
            readOnly 
          />
          <Field 
            label="ID de Ruta" 
            value={route.route_id} 
            readOnly 
          />
        </div>
      </section>

      {/* Estado */}
      <section>
        <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
          <Bus className="w-4 h-4 text-indigo-400" />
          Estado Actual
        </h3>
        <div className="bg-gray-800/50 rounded-lg p-4 space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-gray-400">Bus asignado</span>
            <span className="text-white font-medium">
              {route.assignedBusId ? (
                <span className="flex items-center gap-2">
                  <Bus className="w-4 h-4 text-indigo-400" />
                  {route.assignedBusId}
                </span>
              ) : (
                <span className="text-amber-400 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4" />
                  Sin asignar
                </span>
              )}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-gray-400">Posición en bus</span>
            <span className="text-white font-medium">
              {route.positionInBus !== undefined ? `#${route.positionInBus + 1}` : '-'}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-gray-400">Estado</span>
            <StatusBadge status={route.status} isLocked={route.isLocked} />
          </div>
          <div className="flex justify-between items-center">
            <span className="text-gray-400">Duración</span>
            <span className="text-white font-medium">{route.duration_minutes} minutos</span>
          </div>
        </div>
      </section>

      {/* Coordenadas (solo lectura) */}
      {route.startCoordinates && (
        <section>
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <MapPin className="w-4 h-4 text-indigo-400" />
            Coordenadas
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-gray-800/30 rounded-lg p-3">
              <span className="text-gray-500 text-xs block mb-1">Origen</span>
              <span className="text-gray-300 text-sm font-mono">
                {route.startCoordinates.lat?.toFixed(6) || 'N/A'}, {route.startCoordinates.lon?.toFixed(6) || 'N/A'}
              </span>
            </div>
            <div className="bg-gray-800/30 rounded-lg p-3">
              <span className="text-gray-500 text-xs block mb-1">Destino</span>
              <span className="text-gray-300 text-sm font-mono">
                {route.endCoordinates?.lat?.toFixed(6) || 'N/A'}, {route.endCoordinates?.lon?.toFixed(6) || 'N/A'}
              </span>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function TimesTab({ route, onTimeChange }) {
  const isLocked = route.isLocked;

  return (
    <div className="space-y-6">
      <section>
        <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
          <Clock className="w-4 h-4 text-indigo-400" />
          Horarios de la Ruta
        </h3>
        
        {isLocked && (
          <div className="mb-4 bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 flex items-center gap-2 text-amber-400 text-sm">
            <Lock className="w-4 h-4" />
            La ruta está bloqueada. Desbloquéala para editar los horarios.
          </div>
        )}
        
        <div className="grid grid-cols-2 gap-6">
          {/* Hora de inicio */}
          <div className="bg-gray-800/50 rounded-lg p-4">
            <label className="block text-gray-400 text-sm mb-2">Hora de inicio</label>
            <div className="flex items-center gap-3">
              <input
                type="time"
                value={route.currentStartTime || route.start_time}
                onChange={(e) => onTimeChange('currentStartTime', e.target.value)}
                disabled={isLocked}
                className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white focus:border-indigo-500 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              />
              <span className="text-gray-500 text-sm">Original: {route.start_time}</span>
            </div>
          </div>

          {/* Hora de fin */}
          <div className="bg-gray-800/50 rounded-lg p-4">
            <label className="block text-gray-400 text-sm mb-2">Hora de fin</label>
            <div className="flex items-center gap-3">
              <input
                type="time"
                value={route.currentEndTime || route.end_time}
                onChange={(e) => onTimeChange('currentEndTime', e.target.value)}
                disabled={isLocked}
                className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white focus:border-indigo-500 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              />
              <span className="text-gray-500 text-sm">Original: {route.end_time}</span>
            </div>
          </div>
        </div>

        {/* Duración */}
        <div className="mt-4 bg-gray-800/50 rounded-lg p-4">
          <label className="block text-gray-400 text-sm mb-2">Duración (minutos)</label>
          <div className="flex items-center gap-3">
            <input
              type="number"
              value={route.duration_minutes}
              readOnly
              className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white w-24 opacity-60 cursor-not-allowed"
            />
            <span className="text-gray-400">minutos</span>
            <span className="text-gray-500 text-sm ml-4">
              (Calculada automáticamente)
            </span>
          </div>
        </div>

        {/* Vista previa del horario */}
        <div className="mt-4 bg-indigo-500/10 border border-indigo-500/30 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <span className="text-indigo-300 text-sm">Vista previa del horario</span>
            <span className="text-white font-mono font-medium">
              {route.currentStartTime || route.start_time} - {route.currentEndTime || route.end_time}
            </span>
          </div>
          <div className="mt-2 h-2 bg-gray-800 rounded-full overflow-hidden">
            <div 
              className="h-full bg-indigo-500 rounded-full"
              style={{ width: '100%' }}
            />
          </div>
        </div>
      </section>
    </div>
  );
}

function StopsTab({ route, onUpdate, setHasChanges }) {
  const [stops, setStops] = useState(route.stops || []);
  const isLocked = route.isLocked;

  // Sincronizar stops cuando cambia la ruta
  useEffect(() => {
    setStops(route.stops || []);
  }, [route.stops]);

  const handleStopUpdate = (index, field, value) => {
    if (isLocked) return;
    const newStops = [...stops];
    newStops[index] = { ...newStops[index], [field]: value };
    setStops(newStops);
    onUpdate(prev => ({ ...prev, stops: newStops }));
    setHasChanges(true);
  };

  const handleReorder = (fromIndex, toIndex) => {
    if (isLocked) return;
    const newStops = [...stops];
    const [moved] = newStops.splice(fromIndex, 1);
    newStops.splice(toIndex, 0, moved);
    // Update order numbers
    newStops.forEach((stop, idx) => stop.stop_order = idx + 1);
    setStops(newStops);
    onUpdate(prev => ({ ...prev, stops: newStops }));
    setHasChanges(true);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-white font-semibold flex items-center gap-2">
          <MapPin className="w-4 h-4 text-indigo-400" />
          Paradas ({stops.length})
        </h3>
        <span className="text-gray-500 text-sm">
          {isLocked ? 'Bloqueado' : 'Usa ▲▼ para reordenar'}
        </span>
      </div>

      {isLocked && (
        <div className="mb-4 bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 flex items-center gap-2 text-amber-400 text-sm">
          <Lock className="w-4 h-4" />
          La ruta está bloqueada. Desbloquéala para editar las paradas.
        </div>
      )}

      <div className="space-y-2">
        {stops.length === 0 ? (
          <div className="text-center py-8 text-gray-500 bg-gray-800/30 rounded-lg">
            <MapPin className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No hay paradas definidas para esta ruta</p>
          </div>
        ) : (
          stops.map((stop, index) => (
            <StopItem
              key={stop.stop_id || `stop-${index}`}
              stop={stop}
              index={index}
              total={stops.length}
              isLocked={isLocked}
              onUpdate={(field, value) => handleStopUpdate(index, field, value)}
              onMoveUp={() => index > 0 && handleReorder(index, index - 1)}
              onMoveDown={() => index < stops.length - 1 && handleReorder(index, index + 1)}
            />
          ))
        )}
      </div>
    </div>
  );
}

function StopItem({ stop, index, total, isLocked, onUpdate, onMoveUp, onMoveDown }) {
  return (
    <div className="bg-gray-800/50 rounded-lg p-3 flex items-center gap-3 hover:bg-gray-800/70 transition-colors">
      <div className="flex flex-col">
        <button 
          onClick={onMoveUp} 
          disabled={index === 0 || isLocked} 
          className="text-gray-500 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed p-0.5"
        >
          ▲
        </button>
        <button 
          onClick={onMoveDown} 
          disabled={index === total - 1 || isLocked} 
          className="text-gray-500 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed p-0.5"
        >
          ▼
        </button>
      </div>
      
      <div className="w-8 h-8 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-sm font-bold flex-shrink-0">
        {stop.stop_order || index + 1}
      </div>
      
      <div className="flex-1 min-w-0">
        <input
          type="text"
          value={stop.stop_name || ''}
          onChange={(e) => onUpdate('stop_name', e.target.value)}
          disabled={isLocked}
          className="bg-gray-900 border border-gray-700 rounded px-2 py-1 text-white text-sm w-full focus:border-indigo-500 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
          placeholder="Nombre de la parada"
        />
        {stop.stop_id && (
          <span className="text-gray-500 text-xs mt-0.5 block">ID: {stop.stop_id}</span>
        )}
      </div>
      
      <div className="flex items-center gap-2 text-sm flex-shrink-0">
        <span className="text-gray-500">Tiempo:</span>
        <input
          type="number"
          value={stop.time_from_start || 0}
          onChange={(e) => onUpdate('time_from_start', parseInt(e.target.value) || 0)}
          disabled={isLocked}
          className="bg-gray-900 border border-gray-700 rounded px-2 py-1 text-white w-16 focus:border-indigo-500 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
        />
        <span className="text-gray-500">min</span>
      </div>
      
      {stop.is_school && (
        <span className="bg-blue-500/20 text-blue-400 text-xs px-2 py-1 rounded flex-shrink-0">
          Colegio
        </span>
      )}
    </div>
  );
}

function ModalFooter({ route, onLockToggle, onSave, onClose, onDelete, hasChanges, isSaving }) {
  return (
    <div className="flex items-center justify-between p-5 border-t border-gray-800">
      <div className="flex items-center gap-3">
        <button
          onClick={onLockToggle}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
            route.isLocked
              ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
              : 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
          }`}
        >
          {route.isLocked ? <Lock className="w-4 h-4" /> : <Unlock className="w-4 h-4" />}
          {route.isLocked ? 'Desbloquear ruta' : 'Bloquear ruta'}
        </button>
        
        {!route.isLocked && (
          <button
            onClick={onDelete}
            className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-gray-800 text-gray-400 hover:bg-red-500/20 hover:text-red-400 transition-colors"
            title="Eliminar ruta"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        )}
      </div>
      
      <div className="flex items-center gap-3">
        {route.isLocked && (
          <span className="text-amber-400 text-sm flex items-center gap-1">
            <AlertCircle className="w-4 h-4" />
            Ruta bloqueada
          </span>
        )}
        <button
          onClick={onClose}
          className="px-4 py-2 text-gray-400 hover:text-white transition-colors"
        >
          Cancelar
        </button>
        <button
          onClick={onSave}
          disabled={!hasChanges || route.isLocked || isSaving}
          className="flex items-center gap-2 px-6 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg font-medium transition-colors min-w-[140px] justify-center"
        >
          {isSaving ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Guardando...
            </>
          ) : (
            <>
              <Save className="w-4 h-4" />
              Guardar
            </>
          )}
        </button>
      </div>
    </div>
  );
}

function DeleteConfirmDialog({ routeName, onConfirm, onCancel }) {
  return (
    <div className="absolute inset-0 bg-black/80 backdrop-blur-sm rounded-2xl flex items-center justify-center z-10">
      <div className="bg-[#1a1a23] border border-gray-700 rounded-xl p-6 max-w-sm mx-4">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center">
            <Trash2 className="w-5 h-5 text-red-400" />
          </div>
          <h3 className="text-lg font-semibold text-white">¿Eliminar ruta?</h3>
        </div>
        <p className="text-gray-400 mb-6">
          ¿Estás seguro de que quieres eliminar <strong className="text-white">{routeName}</strong>? 
          Esta acción no se puede deshacer.
        </p>
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-700 transition-colors"
          >
            Cancelar
          </button>
          <button
            onClick={onConfirm}
            className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-500 transition-colors"
          >
            Eliminar
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, readOnly = false }) {
  return (
    <div>
      <label className="block text-gray-400 text-sm mb-1">{label}</label>
      <input
        type="text"
        value={value || ''}
        readOnly={readOnly}
        className={`w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white ${
          readOnly ? 'opacity-60 cursor-not-allowed' : 'focus:border-indigo-500 focus:outline-none'
        }`}
      />
    </div>
  );
}

function StatusBadge({ status, isLocked }) {
  const styles = {
    assigned: 'bg-green-500/20 text-green-400',
    unassigned: 'bg-amber-500/20 text-amber-400',
    locked: 'bg-red-500/20 text-red-400'
  };

  const labels = {
    assigned: 'Asignada',
    unassigned: 'Libre',
    locked: 'Bloqueada'
  };

  const style = isLocked ? styles.locked : styles[status] || styles.unassigned;
  const label = isLocked ? labels.locked : labels[status] || status;

  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${style}`}>
      {label}
    </span>
  );
}

export default RouteEditModal;
