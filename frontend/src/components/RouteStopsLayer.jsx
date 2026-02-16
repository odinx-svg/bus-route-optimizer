import React, { useMemo } from 'react';
import { Polyline, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';

/**
 * Crea icono para el marcador de origen (primera parada)
 */
const createStartIcon = () => {
  return L.divIcon({
    className: 'stop-marker-start',
    html: `
      <div class="stop-marker-start-inner">
        <span>A</span>
      </div>
    `,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -12],
  });
};

/**
 * Crea icono para marcadores de paradas intermedias
 */
const createIntermediateIcon = () => {
  return L.divIcon({
    className: 'stop-marker-intermediate',
    html: `<div class="stop-marker-intermediate-inner"></div>`,
    iconSize: [12, 12],
    iconAnchor: [6, 6],
    popupAnchor: [0, -6],
  });
};

/**
 * Crea icono para el marcador de destino (colegio/última parada)
 */
const createEndIcon = (isSchool = true) => {
  return L.divIcon({
    className: 'stop-marker-end',
    html: `
      <div class="stop-marker-end-inner">
        ${isSchool 
          ? `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-4 h-4">
              <path d="M11.47 3.84a.75.75 0 011.06 0l8.69 8.69a.75.75 0 101.06-1.06l-8.689-8.69a2.25 2.25 0 00-3.182 0l-8.69 8.69a.75.75 0 001.061 1.06l8.69-8.69z" />
              <path d="M12 5.432l8.159 8.159c.03.03.06.058.091.086v6.198c0 1.035-.84 1.875-1.875 1.875H15a.75.75 0 01-.75-.75v-4.5a.75.75 0 00-.75-.75h-3a.75.75 0 00-.75.75V21a.75.75 0 01-.75.75H5.625a1.875 1.875 0 01-1.875-1.875v-6.198a2.29 2.29 0 00.091-.086L12 5.43z" />
            </svg>`
          : '<span>B</span>'
        }
      </div>
    `,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -14],
  });
};

/**
 * Formatea el tiempo desde el inicio de la ruta
 * Convierte minutos a formato legible
 */
const formatTimeFromStart = (minutes) => {
  if (minutes === 0) return 'Inicio';
  if (minutes < 60) return `+${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `+${hours}h ${mins}min`;
};

/**
 * Calcula la hora estimada de llegada a una parada
 */
const calculateArrivalTime = (startTime, timeFromStartMinutes) => {
  if (!startTime) return '--:--';
  
  try {
    const [hours, minutes] = startTime.split(':').map(Number);
    const startDate = new Date();
    startDate.setHours(hours, minutes, 0);
    
    const arrivalDate = new Date(startDate.getTime() + timeFromStartMinutes * 60000);
    
    return arrivalDate.toLocaleTimeString('es-ES', { 
      hour: '2-digit', 
      minute: '2-digit',
      hour12: false 
    });
  } catch (e) {
    return '--:--';
  }
};

/**
 * Componente para renderizar una ruta con sus paradas
 */
const RouteWithStops = ({ 
  routeId, 
  busId,
  stops, 
  positions, // Posiciones de OSRM (geometría real por carretera)
  startTime,
  endTime,
  type,
  color,
  schoolName,
  timeShift = 0,
  isSelected = false 
}) => {
  // Ordenar paradas por tiempo desde inicio
  const sortedStops = useMemo(() => {
    return [...(stops || [])].sort((a, b) => (a.time_from_start || 0) - (b.time_from_start || 0));
  }, [stops]);

  // Usar posiciones de OSRM si están disponibles, sino fallback a líneas rectas entre paradas
  const routePositions = useMemo(() => {
    if (positions && positions.length > 0) {
      return positions; // Geometría real por carretera de OSRM
    }
    // Fallback: líneas rectas entre paradas (solo si OSRM falló)
    return sortedStops.map(stop => [stop.lat, stop.lon]);
  }, [positions, sortedStops]);

  if (sortedStops.length < 2) return null;

  const totalStops = sortedStops.length;

  return (
    <>
      {/* Línea conectando todas las paradas */}
      <Polyline
        positions={routePositions}
        pathOptions={{
          color: color,
          weight: isSelected ? 5 : 3.5,
          opacity: isSelected ? 0.9 : 0.7,
          lineCap: 'round',
          lineJoin: 'round',
        }}
      />

      {/* Marcadores de paradas */}
      {sortedStops.map((stop, index) => {
        const isFirst = index === 0;
        const isLast = index === totalStops - 1;
        const isSchool = stop.is_school || isLast;
        const stopNumber = index + 1;
        
        // Seleccionar icono según tipo de parada
        let icon;
        if (isFirst) {
          icon = createStartIcon();
        } else if (isLast && isSchool) {
          icon = createEndIcon(true);
        } else if (isLast) {
          icon = createEndIcon(false);
        } else {
          icon = createIntermediateIcon();
        }

        const arrivalTime = calculateArrivalTime(startTime, stop.time_from_start || 0);
        const displayTime = timeShift > 0 
          ? calculateArrivalTime(startTime, (stop.time_from_start || 0) - timeShift)
          : arrivalTime;

        return (
          <Marker
            key={`stop-${routeId}-${index}`}
            position={[stop.lat, stop.lon]}
            icon={icon}
          >
            <Popup className="stop-popup">
              <div className="stop-popup-content">
                {/* Header con nombre de parada */}
                <div className="stop-popup-header">
                  <span className="stop-popup-icon">
                    {isFirst ? '🚀' : isLast ? (isSchool ? '🏫' : '🏁') : '📍'}
                  </span>
                  <h3 className="stop-popup-name">{stop.name || `Parada ${stopNumber}`}</h3>
                </div>

                {/* Hora estimada */}
                <div className="stop-popup-time">
                  <span className="stop-popup-time-value">{displayTime}</span>
                  {timeShift > 0 && (
                    <span className="stop-popup-time-adjusted">
                      (original: {arrivalTime})
                    </span>
                  )}
                </div>

                {/* Info de secuencia */}
                <div className="stop-popup-sequence">
                  Parada {stopNumber} de {totalStops}
                </div>

                {/* Divider */}
                <div className="stop-popup-divider" />

                {/* Info de ruta */}
                <div className="stop-popup-route-info">
                  <div className="stop-popup-info-row">
                    <span className="stop-popup-info-label">🚌 Ruta:</span>
                    <span className="stop-popup-info-value">{routeId}</span>
                  </div>
                  <div className="stop-popup-info-row">
                    <span className="stop-popup-info-label">🚐 Bus:</span>
                    <span className="stop-popup-info-value">{busId}</span>
                  </div>
                  {schoolName && (
                    <div className="stop-popup-info-row">
                      <span className="stop-popup-info-label">🏫 Destino:</span>
                      <span className="stop-popup-info-value">{schoolName}</span>
                    </div>
                  )}
                  <div className="stop-popup-info-row">
                    <span className="stop-popup-info-label">⏱️ Hora llegada:</span>
                    <span className="stop-popup-info-value">{endTime}</span>
                  </div>
                  {stop.passengers > 0 && (
                    <div className="stop-popup-info-row">
                      <span className="stop-popup-info-label">👥 Alumnos:</span>
                      <span className="stop-popup-info-value">{stop.passengers}</span>
                    </div>
                  )}
                </div>

                {/* Badge de tipo */}
                <div className="stop-popup-badges">
                  <span className={`stop-popup-badge ${type === 'entry' ? 'badge-entry' : 'badge-exit'}`}>
                    {type === 'entry' ? 'Entrada' : 'Salida'}
                  </span>
                  {isFirst && (
                    <span className="stop-popup-badge badge-start">Origen</span>
                  )}
                  {isLast && (
                    <span className="stop-popup-badge badge-end">Destino</span>
                  )}
                </div>
              </div>
            </Popup>
          </Marker>
        );
      })}
    </>
  );
};

/**
 * Componente principal que renderiza todas las rutas con paradas
 */
const RouteStopsLayer = ({ 
  routes, 
  selectedBusId, 
  selectedRouteId,
  onBusSelect 
}) => {
  if (!routes || routes.length === 0) return null;

  return (
    <>
      {routes.map((route, index) => (
        <RouteWithStops
          key={`route-stops-${route.routeId || index}`}
          routeId={route.routeId}
          busId={route.busId}
          stops={route.stops}
          positions={route.positions} // Geometría real por carretera desde OSRM
          startTime={route.startTime}
          endTime={route.endTime}
          type={route.type}
          color={route.color}
          schoolName={route.school}
          timeShift={route.timeShift}
          isSelected={
            selectedRouteId === route.routeId || 
            selectedBusId === route.busId
          }
        />
      ))}
    </>
  );
};

export default RouteStopsLayer;
