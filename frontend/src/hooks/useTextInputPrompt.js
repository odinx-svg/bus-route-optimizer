import { useCallback, useEffect, useRef, useState } from 'react';

const EMPTY_TEXT_INPUT_MODAL = {
  open: false,
  title: '',
  description: '',
  placeholder: '',
  confirmLabel: 'Aceptar',
  cancelLabel: 'Cancelar',
  allowEmpty: true,
  value: '',
};

export function useTextInputPrompt() {
  const [textInputModal, setTextInputModal] = useState(EMPTY_TEXT_INPUT_MODAL);
  const resolverRef = useRef(null);

  const closeTextInputModal = useCallback((result = { confirmed: false, value: '' }) => {
    setTextInputModal((prev) => ({ ...prev, open: false }));
    const resolver = resolverRef.current;
    resolverRef.current = null;
    if (typeof resolver === 'function') {
      resolver(result);
    }
  }, []);

  const openTextInputModal = useCallback((config = {}) => (
    new Promise((resolve) => {
      resolverRef.current = resolve;
      setTextInputModal({
        open: true,
        title: config.title || 'Introduce un valor',
        description: config.description || '',
        placeholder: config.placeholder || '',
        confirmLabel: config.confirmLabel || 'Aceptar',
        cancelLabel: config.cancelLabel || 'Cancelar',
        allowEmpty: Boolean(config.allowEmpty ?? true),
        value: String(config.defaultValue || ''),
      });
    })
  ), []);

  const setTextInputValue = useCallback((value) => {
    setTextInputModal((prev) => ({ ...prev, value }));
  }, []);

  useEffect(() => () => {
    if (typeof resolverRef.current === 'function') {
      resolverRef.current({ confirmed: false, value: '' });
      resolverRef.current = null;
    }
  }, []);

  return {
    textInputModal,
    openTextInputModal,
    closeTextInputModal,
    setTextInputValue,
  };
}
