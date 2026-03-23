import React from 'react';

export default function TextInputDialog({
  open = false,
  title = '',
  description = '',
  value = '',
  placeholder = '',
  confirmLabel = 'Aceptar',
  cancelLabel = 'Cancelar',
  allowEmpty = true,
  onChange,
  onCancel,
  onConfirm,
}) {
  if (!open) return null;

  const normalizedValue = String(value || '');
  const disabled = !allowEmpty && normalizedValue.trim().length === 0;

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-[#020611]/80 backdrop-blur-[2px]" onClick={onCancel} />
      <div className="relative w-full max-w-md rounded-xl border border-[#253a4f] bg-[#0b141f] p-4 shadow-2xl">
        <h3 className="text-[15px] font-semibold text-white">{title}</h3>
        {description ? (
          <p className="mt-1 text-[12px] text-[#8ba3bd]">{description}</p>
        ) : null}
        <input
          type="text"
          autoFocus
          value={normalizedValue}
          placeholder={placeholder}
          onChange={(event) => onChange?.(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              event.preventDefault();
              onCancel?.();
              return;
            }
            if (event.key === 'Enter' && !disabled) {
              event.preventDefault();
              onConfirm?.();
            }
          }}
          className="mt-3 w-full rounded-lg border border-[#2a4057] bg-[#0a1324] px-3 py-2 text-[13px] text-white outline-none transition focus:border-[#4ecbff]/70"
        />
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-[#2a4057] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9eb2c8] transition hover:bg-white/5"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={disabled}
            className="rounded-md bg-[#2ab5e8] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#03131f] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
