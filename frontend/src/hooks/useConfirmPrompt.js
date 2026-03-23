import { useCallback, useEffect, useRef, useState } from 'react';

const EMPTY_CONFIRM_MODAL = {
  open: false,
  title: '',
  description: '',
  tone: 'info',
  confirmLabel: 'Aceptar',
  cancelLabel: 'Cancelar',
};

export function useConfirmPrompt() {
  const [confirmModal, setConfirmModal] = useState(EMPTY_CONFIRM_MODAL);
  const resolverRef = useRef(null);

  const closeConfirmModal = useCallback((result = { confirmed: false }) => {
    setConfirmModal((prev) => ({ ...prev, open: false }));
    const resolver = resolverRef.current;
    resolverRef.current = null;
    if (typeof resolver === 'function') {
      resolver(result);
    }
  }, []);

  const openConfirmModal = useCallback((config = {}) => (
    new Promise((resolve) => {
      resolverRef.current = resolve;
      setConfirmModal({
        open: true,
        title: config.title || 'Confirmar accion',
        description: config.description || '',
        tone: config.tone || 'info',
        confirmLabel: config.confirmLabel || 'Aceptar',
        cancelLabel: config.cancelLabel || 'Cancelar',
      });
    })
  ), []);

  useEffect(() => () => {
    if (typeof resolverRef.current === 'function') {
      resolverRef.current({ confirmed: false });
      resolverRef.current = null;
    }
  }, []);

  return {
    confirmModal,
    openConfirmModal,
    closeConfirmModal,
  };
}
