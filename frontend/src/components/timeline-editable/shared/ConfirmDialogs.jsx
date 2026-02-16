import React, { useState, useEffect } from 'react';
import { AlertTriangle, Check, X, Trash2, Save, Bus, MapPin, Lock, Unlock, Loader2, Info } from 'lucide-react';

function ModalContainer({ children, onClose, maxWidth = 'sm', closeOnOverlay = true }) {
  const maxWidths = { sm: 'max-w-sm', md: 'max-w-md', lg: 'max-w-lg' };

  useEffect(() => {
    const handleEscape = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handleEscape);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 animate-in fade-in duration-200" onClick={closeOnOverlay ? onClose : undefined}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="relative h-full flex items-center justify-center p-4">
        <div className={`bg-gray-800 rounded-2xl shadow-2xl border border-gray-700 w-full ${maxWidths[maxWidth]} animate-in zoom-in-95`} onClick={(e) => e.stopPropagation()}>
          {children}
        </div>
      </div>
    </div>
  );
}

function ActionButton({ onClick, children, variant = 'primary', loading = false, disabled = false, icon: Icon }) {
  const variants = {
    primary: 'bg-indigo-600 hover:bg-indigo-500 text-white disabled:bg-indigo-800',
    danger: 'bg-red-600 hover:bg-red-500 text-white disabled:bg-red-800',
    success: 'bg-green-600 hover:bg-green-500 text-white disabled:bg-green-800',
    secondary: 'bg-gray-700 hover:bg-gray-600 text-white disabled:bg-gray-800'
  };
  return (
    <button onClick={onClick} disabled={loading || disabled} className={`flex items-center justify-center gap-2 flex-1 py-2.5 px-4 rounded-lg text-sm font-medium transition-all disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]}`}>
      {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : Icon ? <Icon className="w-4 h-4" /> : null}{children}
    </button>
  );
}

export function ConfirmClearBusDialog({ busId, busName, routesCount, onConfirm, onCancel }) {
  const [isLoading, setIsLoading] = useState(false);
  const handleConfirm = async () => { setIsLoading(true); try { await onConfirm(); } finally { setIsLoading(false); } };

  return (
    <ModalContainer onClose={onCancel}>
      <div className="p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-amber-500/20 flex items-center justify-center"><AlertTriangle className="w-5 h-5 text-amber-400" /></div>
          <h3 className="text-white font-bold text-lg">¿Limpiar {busName || `Bus ${busId}`}?</h3>
        </div>
        <p className="text-gray-400 text-sm mb-2">Esto moverá {routesCount || 'todas'} las rutas asignadas al panel de rutas libres.</p>
        <div className="bg-amber-900/20 border border-amber-500/20 rounded-lg p-3 mb-4">
          <div className="flex items-start gap-2">
            <Info className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
            <p className="text-amber-300/80 text-xs">Las rutas no se eliminarán, solo se desasignarán del bus.</p>
          </div>
        </div>
        <div className="flex gap-3">
          <ActionButton onClick={onCancel} variant="secondary" icon={X}>Cancelar</ActionButton>
          <ActionButton onClick={handleConfirm} variant="danger" loading={isLoading} icon={Trash2}>{isLoading ? 'Limpiando...' : 'Limpiar bus'}</ActionButton>
        </div>
      </div>
    </ModalContainer>
  );
}

export function ConfirmSaveDialog({ hasConflicts, conflictCount, conflictDetails = [], onConfirm, onCancel, onReviewConflicts }) {
  const [isLoading, setIsLoading] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const handleConfirm = async () => { setIsLoading(true); try { await onConfirm(); } finally { setIsLoading(false); } };

  return (
    <ModalContainer onClose={onCancel} maxWidth={showDetails ? 'md' : 'sm'}>
      <div className="p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className={`w-10 h-10 rounded-full flex items-center justify-center ${hasConflicts ? 'bg-red-500/20' : 'bg-green-500/20'}`}>
            {hasConflicts ? <AlertTriangle className="w-5 h-5 text-red-400" /> : <Save className="w-5 h-5 text-green-400" />}
          </div>
          <h3 className="text-white font-bold text-lg">{hasConflicts ? '⚠️ Hay conflictos' : 'Guardar horario'}</h3>
        </div>

        <div className="mb-4">
          {hasConflicts ? (
            <>
              <p className="text-gray-400 text-sm mb-2">Se detectaron <span className="text-red-400 font-semibold">{conflictCount} conflictos</span>.</p>
              {conflictDetails.length > 0 && (
                <>
                  <button onClick={() => setShowDetails(!showDetails)} className="text-indigo-400 text-xs hover:text-indigo-300 mb-2">{showDetails ? 'Ocultar' : 'Ver detalles'}</button>
                  {showDetails && (
                    <div className="bg-red-950/30 border border-red-500/20 rounded-lg p-3 max-h-40 overflow-y-auto">
                      <ul className="space-y-2 text-xs">
                        {conflictDetails.map((c, i) => <li key={i} className="text-red-300/80">• {c.message || c}</li>)}
                      </ul>
                    </div>
                  )}
                </>
              )}
              <div className="bg-amber-900/20 border border-amber-500/20 rounded-lg p-3 mt-3">
                <p className="text-amber-300/80 text-xs"><strong>Advertencia:</strong> Guardar con conflictos puede generar horarios inviables.</p>
              </div>
            </>
          ) : (
            <p className="text-gray-400 text-sm">¿Estás seguro de guardar este horario? Los cambios se aplicarán inmediatamente.</p>
          )}
        </div>

        <div className="flex gap-3">
          <ActionButton onClick={onCancel} variant="secondary" icon={X}>Cancelar</ActionButton>
          {hasConflicts && onReviewConflicts && <ActionButton onClick={onReviewConflicts} variant="ghost">Revisar</ActionButton>}
          <ActionButton onClick={handleConfirm} variant={hasConflicts ? 'danger' : 'success'} loading={isLoading} icon={hasConflicts ? AlertTriangle : Check}>
            {isLoading ? 'Guardando...' : hasConflicts ? 'Guardar igual' : 'Guardar'}
          </ActionButton>
        </div>
      </div>
    </ModalContainer>
  );
}

export function ConfirmDeleteRouteDialog({ route, onConfirm, onCancel }) {
  const [isLoading, setIsLoading] = useState(false);
  const handleConfirm = async () => { setIsLoading(true); try { await onConfirm(); } finally { setIsLoading(false); } };

  return (
    <ModalContainer onClose={onCancel}>
      <div className="p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center"><Trash2 className="w-5 h-5 text-red-400" /></div>
          <h3 className="text-white font-bold text-lg">¿Eliminar ruta?</h3>
        </div>
        <div className="bg-gray-900/50 rounded-lg p-3 mb-4">
          <div className="flex items-center gap-2 text-gray-300 text-sm">
            <MapPin className="w-4 h-4 text-indigo-400" />
            <span className="font-medium">{route?.id || route?.nombre || 'Ruta'}</span>
          </div>
        </div>
        <p className="text-red-400/80 text-sm mb-4">Esta acción no se puede deshacer. La ruta se eliminará permanentemente.</p>
        <div className="flex gap-3">
          <ActionButton onClick={onCancel} variant="secondary" icon={X}>Cancelar</ActionButton>
          <ActionButton onClick={handleConfirm} variant="danger" loading={isLoading} icon={Trash2}>{isLoading ? 'Eliminando...' : 'Eliminar'}</ActionButton>
        </div>
      </div>
    </ModalContainer>
  );
}

export function ConfirmMoveRouteDialog({ route, fromBus, toBus, compatibility, onConfirm, onCancel }) {
  const [isLoading, setIsLoading] = useState(false);
  const handleConfirm = async () => { setIsLoading(true); try { await onConfirm(); } finally { setIsLoading(false); } };
  const isCompatible = compatibility?.compatible ?? true;

  return (
    <ModalContainer onClose={onCancel}>
      <div className="p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className={`w-10 h-10 rounded-full flex items-center justify-center ${isCompatible ? 'bg-indigo-500/20' : 'bg-amber-500/20'}`}>
            <Bus className={`w-5 h-5 ${isCompatible ? 'text-indigo-400' : 'text-amber-400'}`} />
          </div>
          <h3 className="text-white font-bold text-lg">Mover ruta</h3>
        </div>

        <div className="space-y-3 mb-4">
          <div className="flex items-center gap-3 text-sm">
            <div className="flex-1 bg-gray-900/50 rounded-lg p-3">
              <p className="text-gray-500 text-xs mb-1">Desde</p>
              <p className="text-gray-300 font-medium flex items-center gap-2"><Bus className="w-4 h-4" />{fromBus?.name || `Bus ${fromBus?.id}`}</p>
            </div>
            <div className="text-gray-500">→</div>
            <div className="flex-1 bg-indigo-900/20 border border-indigo-500/30 rounded-lg p-3">
              <p className="text-indigo-300/60 text-xs mb-1">Hacia</p>
              <p className="text-indigo-300 font-medium flex items-center gap-2"><Bus className="w-4 h-4" />{toBus?.name || `Bus ${toBus?.id}`}</p>
            </div>
          </div>

          {!isCompatible && compatibility?.reason && (
            <div className="bg-amber-900/20 border border-amber-500/30 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                <div>
                  <p className="text-amber-400 text-sm font-medium">Advertencia</p>
                  <p className="text-amber-300/70 text-xs mt-1">{compatibility.reason}</p>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="flex gap-3">
          <ActionButton onClick={onCancel} variant="secondary" icon={X}>Cancelar</ActionButton>
          <ActionButton onClick={handleConfirm} variant={isCompatible ? 'primary' : 'danger'} loading={isLoading} icon={isCompatible ? Check : AlertTriangle}>
            {isLoading ? 'Moviendo...' : isCompatible ? 'Mover' : 'Mover igual'}
          </ActionButton>
        </div>
      </div>
    </ModalContainer>
  );
}

export function ConfirmLockToggleDialog({ isLocking, itemCount = 1, itemType = 'routes', onConfirm, onCancel }) {
  const [isLoading, setIsLoading] = useState(false);
  const handleConfirm = async () => { setIsLoading(true); try { await onConfirm(); } finally { setIsLoading(false); } };
  const Icon = isLocking ? Lock : Unlock;
  const titleText = isLocking ? 'Bloquear' : 'Desbloquear';

  return (
    <ModalContainer onClose={onCancel}>
      <div className="p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className={`w-10 h-10 rounded-full flex items-center justify-center ${isLocking ? 'bg-amber-500/20' : 'bg-green-500/20'}`}>
            <Icon className={`w-5 h-5 ${isLocking ? 'text-amber-400' : 'text-green-400'}`} />
          </div>
          <h3 className="text-white font-bold text-lg">{titleText} {itemCount} {itemType === 'routes' ? 'rutas' : 'buses'}</h3>
        </div>
        <p className="text-gray-400 text-sm mb-4">
          {isLocking ? 'Las rutas bloqueadas no podrán ser modificadas hasta que se desbloqueen.' : 'Las rutas desbloqueadas podrán ser editadas libremente.'}
        </p>
        <div className="flex gap-3">
          <ActionButton onClick={onCancel} variant="secondary" icon={X}>Cancelar</ActionButton>
          <ActionButton onClick={handleConfirm} variant={isLocking ? 'primary' : 'success'} loading={isLoading} icon={Icon}>
            {isLoading ? 'Procesando...' : titleText}
          </ActionButton>
        </div>
      </div>
    </ModalContainer>
  );
}

export function ConfirmUnsavedChangesDialog({ changeCount = 0, onSave, onDiscard, onCancel }) {
  useEffect(() => {
    const handleBeforeUnload = (e) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, []);

  return (
    <ModalContainer onClose={onCancel}>
      <div className="p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-amber-500/20 flex items-center justify-center"><AlertTriangle className="w-5 h-5 text-amber-400" /></div>
          <h3 className="text-white font-bold text-lg">Cambios sin guardar</h3>
        </div>
        <p className="text-gray-400 text-sm mb-2">Tienes {changeCount > 0 ? `${changeCount} cambios` : 'cambios'} sin guardar.</p>
        <p className="text-gray-500 text-xs mb-4">¿Qué deseas hacer? Los cambios no guardados se perderán.</p>
        <div className="flex gap-2 flex-col">
          <ActionButton onClick={onSave} variant="success" icon={Save}>Guardar cambios</ActionButton>
          <div className="flex gap-2">
            <ActionButton onClick={onCancel} variant="secondary">Cancelar</ActionButton>
            <ActionButton onClick={onDiscard} variant="danger" icon={Trash2}>Descartar</ActionButton>
          </div>
        </div>
      </div>
    </ModalContainer>
  );
}

export function GenericConfirmDialog({ title, description, icon: Icon, iconColor = 'indigo', confirmText = 'Confirmar', cancelText = 'Cancelar', onConfirm, onCancel, confirmVariant = 'primary', isLoading = false }) {
  const [loading, setLoading] = useState(false);
  const colorClasses = { indigo: 'bg-indigo-500/20 text-indigo-400', red: 'bg-red-500/20 text-red-400', amber: 'bg-amber-500/20 text-amber-400', green: 'bg-green-500/20 text-green-400' };
  
  const handleConfirm = async () => { setLoading(true); try { await onConfirm(); } finally { setLoading(false); } };

  return (
    <ModalContainer onClose={onCancel}>
      <div className="p-6">
        <div className="flex items-center gap-3 mb-4">
          {Icon && <div className={`w-10 h-10 rounded-full flex items-center justify-center ${colorClasses[iconColor]}`}><Icon className="w-5 h-5" /></div>}
          <h3 className="text-white font-bold text-lg">{title}</h3>
        </div>
        <p className="text-gray-400 text-sm mb-6">{description}</p>
        <div className="flex gap-3">
          <ActionButton onClick={onCancel} variant="secondary">{cancelText}</ActionButton>
          <ActionButton onClick={handleConfirm} variant={confirmVariant} loading={loading || isLoading}>{confirmText}</ActionButton>
        </div>
      </div>
    </ModalContainer>
  );
}

export default {
  ConfirmClearBusDialog, ConfirmSaveDialog, ConfirmDeleteRouteDialog,
  ConfirmMoveRouteDialog, ConfirmLockToggleDialog, ConfirmUnsavedChangesDialog,
  GenericConfirmDialog
};
