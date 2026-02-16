import { useState, useEffect, useRef, useCallback } from 'react';

export const AUTO_SAVE_STATUS = {
  IDLE: 'idle', SAVING: 'saving', SAVED: 'saved', ERROR: 'error', DIRTY: 'dirty'
};

const DEFAULT_INTERVAL = 30000;
const MAX_RETRIES = 3;

export function useAutoSave({
  data, onSave, interval = DEFAULT_INTERVAL, enabled = true,
  storageKey = 'timeline_autosave_draft', validateBeforeSave, maxRetries = MAX_RETRIES,
  onError, onSuccess
}) {
  const [status, setStatus] = useState(AUTO_SAVE_STATUS.IDLE);
  const [lastSaved, setLastSaved] = useState(null);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);

  const dataRef = useRef(data);
  const saveTimeoutRef = useRef(null);
  const isSavingRef = useRef(false);
  const previousDataRef = useRef(null);

  useEffect(() => { dataRef.current = data; }, [data]);

  const hasChanges = useCallback(() => JSON.stringify(dataRef.current) !== JSON.stringify(previousDataRef.current), []);

  const saveToLocalStorage = useCallback((dataToSave) => {
    try {
      localStorage.setItem(storageKey, JSON.stringify({ data: dataToSave, timestamp: Date.now() }));
    } catch (e) { console.warn('Error saving to localStorage:', e); }
  }, [storageKey]);

  const clearLocalStorage = useCallback(() => {
    try { localStorage.removeItem(storageKey); } catch (e) { console.warn('Error clearing localStorage:', e); }
  }, [storageKey]);

  const performSave = useCallback(async (isBackground = false) => {
    if (isSavingRef.current) return;
    if (!hasChanges() && !isBackground) return;

    if (validateBeforeSave) {
      const validation = validateBeforeSave(dataRef.current);
      if (!validation.valid) {
        setError(validation.error || 'Validación fallida');
        setStatus(AUTO_SAVE_STATUS.ERROR);
        return;
      }
    }

    isSavingRef.current = true;
    setStatus(AUTO_SAVE_STATUS.SAVING);
    setError(null);

    try {
      saveToLocalStorage(dataRef.current);
      if (onSave) await onSave(dataRef.current);

      previousDataRef.current = dataRef.current;
      setLastSaved(new Date());
      setStatus(AUTO_SAVE_STATUS.SAVED);
      setRetryCount(0);
      setTimeout(() => { if (status === AUTO_SAVE_STATUS.SAVED) setStatus(AUTO_SAVE_STATUS.IDLE); }, 2000);
      onSuccess?.();
    } catch (err) {
      console.error('Auto-save error:', err);
      setError(err.message || 'Error al guardar');
      setStatus(AUTO_SAVE_STATUS.ERROR);
      if (retryCount < maxRetries) {
        setTimeout(() => { setRetryCount(p => p + 1); performSave(isBackground); }, Math.pow(2, retryCount) * 1000);
      }
      onError?.(err);
    } finally {
      isSavingRef.current = false;
    }
  }, [hasChanges, validateBeforeSave, onSave, saveToLocalStorage, retryCount, maxRetries, onSuccess, onError, status]);

  // Periodic save
  useEffect(() => {
    if (!enabled || !interval) return;
    saveTimeoutRef.current = setInterval(() => { if (hasChanges()) { setStatus(AUTO_SAVE_STATUS.DIRTY); performSave(true); } }, interval);
    return () => { if (saveTimeoutRef.current) clearInterval(saveTimeoutRef.current); };
  }, [enabled, interval, hasChanges, performSave]);

  // Visibility/Unload handlers
  useEffect(() => {
    if (!enabled) return;
    const handleVisibilityChange = () => { if (document.hidden && hasChanges()) saveToLocalStorage(dataRef.current); };
    const handleBeforeUnload = (e) => { if (hasChanges()) { saveToLocalStorage(dataRef.current); e.preventDefault(); e.returnValue = ''; } };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [enabled, hasChanges, saveToLocalStorage]);

  const checkForDraft = useCallback(() => {
    try {
      const draftJson = localStorage.getItem(storageKey);
      if (draftJson) {
        const draft = JSON.parse(draftJson);
        if (Date.now() - draft.timestamp < 24 * 60 * 60 * 1000) return draft;
        clearLocalStorage();
      }
    } catch (e) { console.warn('Error reading draft:', e); }
    return null;
  }, [storageKey, clearLocalStorage]);

  const restoreDraft = useCallback(() => {
    const draft = checkForDraft();
    return draft ? draft.data : null;
  }, [checkForDraft]);

  const discardDraft = useCallback(() => {
    clearLocalStorage();
    setStatus(AUTO_SAVE_STATUS.IDLE);
    setLastSaved(null);
    setError(null);
  }, [clearLocalStorage]);

  const saveNow = useCallback(async () => { await performSave(false); }, [performSave]);

  useEffect(() => { if (enabled && checkForDraft()) setStatus(AUTO_SAVE_STATUS.DIRTY); }, [enabled, checkForDraft]);

  const getTimeSinceLastSave = useCallback(() => {
    if (!lastSaved) return null;
    const diff = Date.now() - lastSaved.getTime();
    if (diff < 60000) return 'hace unos segundos';
    if (diff < 3600000) return `hace ${Math.floor(diff / 60000)} min`;
    return `hace ${Math.floor(diff / 3600000)}h`;
  }, [lastSaved]);

  return { status, lastSaved, error, retryCount, hasDraft: checkForDraft() !== null, saveNow, restoreDraft, discardDraft, getTimeSinceLastSave, isDirty: status === AUTO_SAVE_STATUS.DIRTY || status === AUTO_SAVE_STATUS.ERROR };
}

export function AutoSaveIndicator({ status, lastSaved, error, className = '' }) {
  const configs = {
    [AUTO_SAVE_STATUS.IDLE]: { icon: null, text: '', className: 'opacity-0' },
    [AUTO_SAVE_STATUS.DIRTY]: { icon: '•', text: 'Cambios sin guardar', className: 'text-amber-400' },
    [AUTO_SAVE_STATUS.SAVING]: { icon: '⟳', text: 'Guardando...', className: 'text-indigo-400 animate-pulse' },
    [AUTO_SAVE_STATUS.SAVED]: { icon: '✓', text: lastSaved ? `Guardado` : 'Guardado', className: 'text-green-400' },
    [AUTO_SAVE_STATUS.ERROR]: { icon: '✕', text: error || 'Error al guardar', className: 'text-red-400' }
  };

  const config = configs[status] || configs[AUTO_SAVE_STATUS.IDLE];
  if (status === AUTO_SAVE_STATUS.IDLE) return null;

  return (
    <div className={`flex items-center gap-2 text-xs transition-all ${config.className} ${className}`}>
      <span>{config.icon}</span>
      <span>{config.text}</span>
    </div>
  );
}

export default useAutoSave;
