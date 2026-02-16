import React from 'react';

/**
 * Línea vertical que separa las horas en el timeline
 */
export function HourLine({ hour, hourRange }) {
  const totalHours = hourRange.end - hourRange.start + 1;
  const leftPercent = ((hour - hourRange.start) / totalHours) * 100;

  return (
    <div
      className="absolute top-0 bottom-0 w-px bg-gray-700/30 pointer-events-none"
      style={{ left: `${leftPercent}%` }}
    >
      {/* Etiqueta de hora en la parte inferior */}
      <span className="absolute bottom-0 left-1 text-[9px] text-gray-600">
        {hour.toString().padStart(2, '0')}:00
      </span>
    </div>
  );
}
