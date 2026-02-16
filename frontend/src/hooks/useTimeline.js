import { useMemo } from 'react';

export function useTimeline(schedule, hourRange = [6, 22]) {
  return useMemo(() => {
    const [startHour, endHour] = hourRange;
    const totalHours = endHour - startHour;
    
    // DEBUG: Log primera ruta
    if (schedule.length > 0 && schedule[0].items.length > 0) {
      const firstItem = schedule[0].items[0];
      const start = timeToMinutes(firstItem.start_time);
      console.log('Timeline Debug:', {
        start_time: firstItem.start_time,
        parsedMinutes: start,
        hourRange,
        calculatedLeft: ((start / 60) - startHour) / totalHours * 100
      });
    }
    
    // Calcular posición y ancho de cada ruta
    const busesWithPositions = schedule.map(bus => ({
      ...bus,
      items: bus.items.map(item => {
        const start = timeToMinutes(item.start_time);
        const end = timeToMinutes(item.end_time);
        
        return {
          ...item,
          left: ((start / 60) - startHour) / totalHours * 100,
          width: ((end - start) / 60) / totalHours * 100,
          startMinutes: start,
          endMinutes: end
        };
      })
    }));
    
    // Generar marcas de hora
    const hourMarks = [];
    for (let h = startHour; h <= endHour; h++) {
      hourMarks.push({
        hour: h,
        left: ((h - startHour) / totalHours) * 100
      });
    }
    
    return { busesWithPositions, hourMarks, totalHours };
  }, [schedule, hourRange]);
}

function timeToMinutes(timeStr) {
  // Manejar formatos: "HH:MM", "HH:MM:SS", o "HH:MM:SS.mmm"
  const parts = timeStr.split(':');
  const hours = parseInt(parts[0], 10);
  const minutes = parseInt(parts[1], 10);
  return hours * 60 + minutes;
}
