import { useState, useCallback, useRef, useEffect } from 'react';

const DEFAULT_OPTIONS = { maxHistory: 50, debounceMs: 500, persistKey: null };

export function useUndoRedo(initialState, options = {}) {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  const [state, setState] = useState(initialState);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  const historyRef = useRef([{ state: initialState, description: 'Estado inicial', timestamp: Date.now() }]);
  const currentIndexRef = useRef(0);
  const debounceTimerRef = useRef(null);
  const lastGroupRef = useRef(null);

  const updateFlags = useCallback(() => {
    setCanUndo(currentIndexRef.current > 0);
    setCanRedo(currentIndexRef.current < historyRef.current.length - 1);
  }, []);

  const persistHistory = useCallback(() => {
    if (!opts.persistKey) return;
    try {
      sessionStorage.setItem(opts.persistKey, JSON.stringify({ history: historyRef.current, currentIndex: currentIndexRef.current, savedAt: Date.now() }));
    } catch (e) { console.warn('Error persisting history:', e); }
  }, [opts.persistKey]);

  const restoreHistory = useCallback(() => {
    if (!opts.persistKey) return null;
    try {
      const data = sessionStorage.getItem(opts.persistKey);
      if (data) {
        const parsed = JSON.parse(data);
        if (Date.now() - parsed.savedAt < 3600000) return parsed;
      }
    } catch (e) { console.warn('Error restoring history:', e); }
    return null;
  }, [opts.persistKey]);

  const addToHistory = useCallback((newState, description = 'Acción', group = null) => {
    if (currentIndexRef.current < historyRef.current.length - 1) {
      historyRef.current = historyRef.current.slice(0, currentIndexRef.current + 1);
    }

    const lastEntry = historyRef.current[historyRef.current.length - 1];
    const shouldGroup = group && lastGroupRef.current === group && Date.now() - lastEntry.timestamp < opts.debounceMs;

    if (shouldGroup) {
      historyRef.current[historyRef.current.length - 1] = { state: newState, description, timestamp: Date.now(), group };
    } else {
      historyRef.current.push({ state: newState, description, timestamp: Date.now(), group });
      if (historyRef.current.length > opts.maxHistory) historyRef.current.shift();
    }

    currentIndexRef.current = historyRef.current.length - 1;
    lastGroupRef.current = group;
    setState(newState);
    updateFlags();
    persistHistory();
    opts.onChange?.(newState);
  }, [opts.debounceMs, opts.maxHistory, opts.onChange, updateFlags, persistHistory]);

  const undo = useCallback(() => {
    if (currentIndexRef.current <= 0) return;
    currentIndexRef.current--;
    const entry = historyRef.current[currentIndexRef.current];
    setState(entry.state);
    updateFlags();
    persistHistory();
    opts.onChange?.(entry.state);
    return entry;
  }, [updateFlags, persistHistory]);

  const redo = useCallback(() => {
    if (currentIndexRef.current >= historyRef.current.length - 1) return;
    currentIndexRef.current++;
    const entry = historyRef.current[currentIndexRef.current];
    setState(entry.state);
    updateFlags();
    persistHistory();
    opts.onChange?.(entry.state);
    return entry;
  }, [updateFlags, persistHistory]);

  const goTo = useCallback((index) => {
    if (index < 0 || index >= historyRef.current.length) return;
    currentIndexRef.current = index;
    const entry = historyRef.current[index];
    setState(entry.state);
    updateFlags();
    persistHistory();
    opts.onChange?.(entry.state);
    return entry;
  }, [updateFlags, persistHistory]);

  const reset = useCallback((newInitialState) => {
    historyRef.current = [{ state: newInitialState, description: 'Estado inicial', timestamp: Date.now() }];
    currentIndexRef.current = 0;
    lastGroupRef.current = null;
    setState(newInitialState);
    updateFlags();
    persistHistory();
  }, [updateFlags, persistHistory]);

  const getHistory = useCallback(() => historyRef.current.map((entry, index) => ({ ...entry, index, isCurrent: index === currentIndexRef.current })), []);

  useEffect(() => {
    const persisted = restoreHistory();
    if (persisted) {
      historyRef.current = persisted.history;
      currentIndexRef.current = persisted.currentIndex;
      const entry = historyRef.current[currentIndexRef.current];
      if (entry) { setState(entry.state); updateFlags(); }
    }
  }, [restoreHistory, updateFlags]);

  useEffect(() => () => { if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current); }, []);

  return { state, canUndo, canRedo, setState: (s, d, g) => addToHistory(s, d, g), undo, redo, goTo, reset, getHistory, historyLength: historyRef.current.length, currentIndex: currentIndexRef.current };
}

export function HistoryPanel({ history, currentIndex, onSelect, onClear, className = '' }) {
  const panelRef = useRef(null);

  useEffect(() => {
    const current = panelRef.current?.querySelector(`[data-index="${currentIndex}"]`);
    current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [currentIndex]);

  if (!history || history.length <= 1) {
    return (
      <div className={`text-center py-8 text-gray-500 ${className}`}>
        <p className="text-sm">Sin historial de cambios</p>
      </div>
    );
  }

  return (
    <div className={`flex flex-col h-full ${className}`}>
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700">
        <h3 className="text-sm font-medium text-gray-300">Historial</h3>
        {onClear && <button onClick={onClear} className="text-xs text-gray-500 hover:text-gray-300">Limpiar</button>}
      </div>
      <div ref={panelRef} className="flex-1 overflow-y-auto py-2">
        {history.map((entry, index) => {
          const isCurrent = index === currentIndex;
          const isPast = index < currentIndex;
          return (
            <button key={index} data-index={index} onClick={() => onSelect?.(index)} className={`w-full px-4 py-2 text-left flex items-center gap-3 transition-colors ${isCurrent ? 'bg-indigo-600/20 border-l-2 border-indigo-500' : 'border-l-2 border-transparent hover:bg-gray-800/50'}`}>
              <span className={`text-xs ${isPast ? 'text-gray-500' : 'text-gray-600'}`}>{index + 1}</span>
              <span className={`text-sm truncate ${isCurrent ? 'text-indigo-300' : isPast ? 'text-gray-400' : 'text-gray-600'}`}>{entry.description}</span>
              <span className="text-xs text-gray-600 ml-auto">{new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
            </button>
          );
        })}
      </div>
      <div className="px-4 py-2 border-t border-gray-700 text-xs text-gray-500">{currentIndex + 1} de {history.length} estados</div>
    </div>
  );
}

export function UndoRedoButtons({ canUndo, canRedo, onUndo, onRedo, className = '' }) {
  return (
    <div className={`flex items-center gap-1 ${className}`}>
      <button onClick={onUndo} disabled={!canUndo} title="Deshacer (Ctrl+Z)" className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-700 disabled:opacity-30 transition-colors">
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" /></svg>
      </button>
      <button onClick={onRedo} disabled={!canRedo} title="Rehacer (Ctrl+Shift+Z)" className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-700 disabled:opacity-30 transition-colors">
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 10h-10a8 8 0 00-8 8v2M21 10l-6 6m6-6l6-6" /></svg>
      </button>
    </div>
  );
}

export default useUndoRedo;
