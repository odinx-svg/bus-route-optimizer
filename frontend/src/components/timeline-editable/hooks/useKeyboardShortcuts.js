import { useEffect, useRef, useCallback } from 'react';

const MODIFIERS = ['Control', 'Alt', 'Shift', 'Meta'];

function isEditing() {
  const active = document.activeElement;
  if (!active) return false;
  const tag = active.tagName.toLowerCase();
  return active.isContentEditable || ['input', 'textarea', 'select'].includes(tag);
}

function normalizeKey(key) {
  const map = { 'esc': 'escape', 'del': 'delete', 'cmd': 'meta', 'return': 'enter' };
  return map[key.toLowerCase()] || key.toLowerCase();
}

export function useKeyboardShortcuts({
  onSave, onUndo, onRedo, onSelectAll, onDelete, onCopy, onPaste, onCut,
  onNavigateUp, onNavigateDown, onNavigateLeft, onNavigateRight,
  onToggleLock, onZoomIn, onZoomOut, onZoomReset, onToggleView, onFocusSearch, onToggleHelp,
  enabled = true, preventDefault = true, ignoreWhileEditing = true, debounceMs = 0
}) {
  const debounceTimer = useRef(null);
  const pressedKeys = useRef(new Set());

  const debouncedCallback = useCallback((callback) => {
    if (!debounceMs || debounceMs <= 0) return callback;
    return (...args) => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
      debounceTimer.current = setTimeout(() => callback(...args), debounceMs);
    };
  }, [debounceMs]);

  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (e) => {
      if (ignoreWhileEditing && isEditing()) {
        if (e.key !== 'Escape' && !e.ctrlKey && !e.metaKey) return;
      }

      const key = normalizeKey(e.key);
      const ctrl = e.ctrlKey || e.metaKey;
      const shift = e.shiftKey;

      pressedKeys.current.add(key);

      const isCombo = (k, opts = {}) => {
        if (key !== normalizeKey(k)) return false;
        if (opts.ctrl !== undefined && opts.ctrl !== ctrl) return false;
        if (opts.shift !== undefined && opts.shift !== shift) return false;
        return true;
      };

      // Save: Ctrl+S
      if (isCombo('s', { ctrl: true }) && onSave) {
        if (preventDefault) e.preventDefault();
        debouncedCallback(onSave)();
        return;
      }

      // Undo: Ctrl+Z
      if (isCombo('z', { ctrl: true, shift: false }) && onUndo) {
        if (preventDefault) e.preventDefault();
        debouncedCallback(onUndo)();
        return;
      }

      // Redo: Ctrl+Shift+Z or Ctrl+Y
      if ((isCombo('z', { ctrl: true, shift: true }) || isCombo('y', { ctrl: true })) && onRedo) {
        if (preventDefault) e.preventDefault();
        debouncedCallback(onRedo)();
        return;
      }

      // Select All: Ctrl+A
      if (isCombo('a', { ctrl: true }) && onSelectAll) {
        if (preventDefault) e.preventDefault();
        debouncedCallback(onSelectAll)();
        return;
      }

      // Delete
      if ((key === 'delete' || key === 'backspace') && onDelete) {
        if (preventDefault) e.preventDefault();
        debouncedCallback(onDelete)();
        return;
      }

      // Copy/Paste/Cut
      if (isCombo('c', { ctrl: true }) && onCopy) { if (preventDefault) e.preventDefault(); debouncedCallback(onCopy)(); return; }
      if (isCombo('v', { ctrl: true }) && onPaste) { if (preventDefault) e.preventDefault(); debouncedCallback(onPaste)(); return; }
      if (isCombo('x', { ctrl: true }) && onCut) { if (preventDefault) e.preventDefault(); debouncedCallback(onCut)(); return; }

      // Search: Ctrl+F or /
      if ((isCombo('f', { ctrl: true }) || (key === '/' && !ctrl)) && onFocusSearch) {
        if (preventDefault) e.preventDefault();
        debouncedCallback(onFocusSearch)();
        return;
      }

      // Navigation
      if (key === 'arrowup' && onNavigateUp) { debouncedCallback(onNavigateUp)(); return; }
      if (key === 'arrowdown' && onNavigateDown) { debouncedCallback(onNavigateDown)(); return; }
      if (key === 'arrowleft' && onNavigateLeft) { debouncedCallback(onNavigateLeft)(); return; }
      if (key === 'arrowright' && onNavigateRight) { debouncedCallback(onNavigateRight)(); return; }

      // Timeline specific
      if (key === 'l' && onToggleLock && !ctrl) { if (preventDefault) e.preventDefault(); debouncedCallback(onToggleLock)(); return; }
      if ((isCombo('=', { ctrl: true })) && onZoomIn) { if (preventDefault) e.preventDefault(); debouncedCallback(onZoomIn)(); return; }
      if (isCombo('-', { ctrl: true }) && onZoomOut) { if (preventDefault) e.preventDefault(); debouncedCallback(onZoomOut)(); return; }
      if (isCombo('0', { ctrl: true }) && onZoomReset) { if (preventDefault) e.preventDefault(); debouncedCallback(onZoomReset)(); return; }
      if (key === 'v' && onToggleView && !ctrl) { if (preventDefault) e.preventDefault(); debouncedCallback(onToggleView)(); return; }
      if ((key === '?' || isCombo('/', { shift: true })) && onToggleHelp) { if (preventDefault) e.preventDefault(); debouncedCallback(onToggleHelp)(); return; }

      // Escape
      if (key === 'escape') {
        document.dispatchEvent(new CustomEvent('escape-pressed'));
      }
    };

    const handleKeyUp = (e) => pressedKeys.current.delete(normalizeKey(e.key));

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, [enabled, preventDefault, ignoreWhileEditing, debounceMs, onSave, onUndo, onRedo, onSelectAll, onDelete, onCopy, onPaste, onCut, onFocusSearch, onNavigateUp, onNavigateDown, onNavigateLeft, onNavigateRight, onToggleLock, onZoomIn, onZoomOut, onZoomReset, onToggleView, onToggleHelp]);

  return { isKeyPressed: (key) => pressedKeys.current.has(normalizeKey(key)), getPressedKeys: () => Array.from(pressedKeys.current) };
}

export function KeyboardShortcutsHelp({ isOpen, onClose }) {
  useEffect(() => {
    const handleEscape = (e) => { if (e.key === 'Escape') onClose(); };
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }
    return () => { document.removeEventListener('keydown', handleEscape); document.body.style.overflow = ''; };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const shortcuts = [
    { category: 'General', items: [
      { key: 'Ctrl + S', desc: 'Guardar cambios' },
      { key: 'Ctrl + Z', desc: 'Deshacer' },
      { key: 'Ctrl + Shift + Z', desc: 'Rehacer' },
      { key: 'Ctrl + A', desc: 'Seleccionar todo' },
      { key: 'Delete', desc: 'Eliminar seleccionado' },
      { key: '/', desc: 'Buscar' },
      { key: '?', desc: 'Mostrar atajos' }
    ]},
    { category: 'Timeline', items: [
      { key: 'L', desc: 'Bloquear/desbloquear' },
      { key: 'V', desc: 'Cambiar vista' },
      { key: 'Ctrl + +', desc: 'Zoom in' },
      { key: 'Ctrl + -', desc: 'Zoom out' },
      { key: 'Ctrl + 0', desc: 'Reset zoom' }
    ]},
    { category: 'Navegación', items: [
      { key: '↑ ↓ ← →', desc: 'Mover selección' },
      { key: 'Escape', desc: 'Cerrar/cancelar' }
    ]}
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-in fade-in">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-gray-800 rounded-2xl shadow-2xl border border-gray-700 max-w-lg w-full max-h-[80vh] overflow-auto animate-in zoom-in-95">
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold text-white">Atajos de teclado</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-white">✕</button>
          </div>
          <div className="space-y-6">
            {shortcuts.map(cat => (
              <div key={cat.category}>
                <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">{cat.category}</h3>
                <div className="space-y-2">
                  {cat.items.map((item, i) => (
                    <div key={i} className="flex items-center justify-between py-2 border-b border-gray-700/50 last:border-0">
                      <span className="text-gray-300 text-sm">{item.desc}</span>
                      <kbd className="px-2 py-1 bg-gray-700 text-gray-300 text-xs rounded font-mono">{item.key}</kbd>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <p className="text-gray-500 text-xs mt-6 text-center">Presiona <kbd className="px-1.5 py-0.5 bg-gray-700 rounded">Escape</kbd> para cerrar</p>
        </div>
      </div>
    </div>
  );
}

export default useKeyboardShortcuts;
