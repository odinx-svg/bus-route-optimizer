/**
 * Utilidades para el timeline editable
 */

/**
 * Convierte tiempo "HH:mm" a minutos desde medianoche
 * @param {string} time - Tiempo en formato "HH:mm"
 * @returns {number} Minutos desde medianoche
 */
export function timeToMinutes(time) {
  if (!time) return 0;
  const [hours, minutes] = time.split(':').map(Number);
  return hours * 60 + minutes;
}

/**
 * Convierte minutos desde medianoche a "HH:mm"
 * @param {number} minutes - Minutos desde medianoche
 * @returns {string} Tiempo en formato "HH:mm"
 */
export function minutesToTime(minutes) {
  const hrs = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}`;
}

/**
 * Genera un array de horas a partir de un rango
 * @param {Object} hourRange - { start: number, end: number }
 * @returns {number[]} Array de horas
 */
export function generateHours(hourRange) {
  const hours = [];
  for (let h = hourRange.start; h <= hourRange.end; h++) {
    hours.push(h);
  }
  return hours;
}

/**
 * Agrupa rutas por hora para mostrarlas en la drop zone
 * @param {Array} routes - Lista de rutas del bus
 * @param {number} hour - Hora a verificar
 * @returns {Array} Rutas que caen en esa hora
 */
export function getRoutesInHour(routes, hour) {
  if (!routes || !Array.isArray(routes)) return [];
  
  return routes.filter(route => {
    if (!route.currentStartTime || !route.currentEndTime) return false;
    
    const startHour = parseInt(route.currentStartTime.split(':')[0]);
    const endHour = parseInt(route.currentEndTime.split(':')[0]);
    return startHour <= hour && hour <= endHour;
  });
}

/**
 * Calcula el total de horas en el rango
 * @param {Object} hourRange - { start: number, end: number }
 * @returns {number} Total de horas
 */
export function getTotalHours(hourRange) {
  return hourRange.end - hourRange.start + 1;
}

/**
 * Formatea una hora para mostrar (ej: 5 -> "05:00")
 * @param {number} hour
 * @returns {string} Hora formateada
 */
export function formatHour(hour) {
  return `${hour.toString().padStart(2, '0')}:00`;
}
