import React from 'react';

const TONE_BADGE_CLASS = {
  info: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-100',
  warning: 'border-amber-500/30 bg-amber-500/10 text-amber-100',
  danger: 'border-rose-500/30 bg-rose-500/10 text-rose-100',
};

const TONE_BUTTON_CLASS = {
  info: 'bg-[#2ab5e8] text-[#03131f] hover:brightness-110',
  warning: 'bg-amber-400 text-[#1a1203] hover:brightness-110',
  danger: 'bg-rose-500 text-white hover:bg-rose-400',
};

export default function ConfirmDialog({
  open = false,
  title = '',
  description = '',
  tone = 'danger',
  confirmLabel = 'Confirmar',
  cancelLabel = 'Cancelar',
  badgeLabel = 'Confirmacion',
  onCancel,
  onConfirm,
}) {
  if (!open) return null;

  const badgeClass = TONE_BADGE_CLASS[tone] || TONE_BADGE_CLASS.info;
  const confirmClass = TONE_BUTTON_CLASS[tone] || TONE_BUTTON_CLASS.info;

  return (
    <div className="fixed inset-0 z-[1200] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-[#020611]/80 backdrop-blur-[2px]" onClick={onCancel} />
      <div className="relative w-full max-w-lg rounded-xl border border-[#253a4f] bg-[#0b141f] p-4 shadow-2xl">
        <div className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] ${badgeClass}`}>
          {badgeLabel}
        </div>
        <h3 className="mt-3 text-[16px] font-semibold text-white">{title}</h3>
        {description ? (
          <p className="mt-2 whitespace-pre-line text-[12px] leading-relaxed text-[#8ba3bd]">{description}</p>
        ) : null}
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
            className={`rounded-md px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] transition ${confirmClass}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
