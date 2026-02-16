const toNonNegativeInt = (value) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 0;
  return Math.max(0, Math.round(parsed));
};

const getStopsPeakPassengers = (stops = []) => {
  if (!Array.isArray(stops) || stops.length === 0) return 0;
  return stops.reduce((peak, stop) => {
    const passengers = toNonNegativeInt(stop?.passengers);
    return passengers > peak ? passengers : peak;
  }, 0);
};

export const buildRouteCapacityMap = (routes = []) => {
  const map = new Map();
  (routes || []).forEach((route) => {
    if (!route) return;
    const routeId = String(route.id || route.route_id || '').trim();
    if (!routeId) return;
    const directCapacity = toNonNegativeInt(route.capacity_needed ?? route.capacityNeeded);
    const fallbackCapacity = getStopsPeakPassengers(route.stops || []);
    map.set(routeId, directCapacity > 0 ? directCapacity : fallbackCapacity);
  });
  return map;
};

export const buildRouteVehicleCapacityMap = (routes = []) => {
  const map = new Map();
  (routes || []).forEach((route) => {
    if (!route) return;
    const routeId = String(route.id || route.route_id || '').trim();
    if (!routeId) return;
    const maxSeats = toNonNegativeInt(
      route.vehicle_capacity_max ??
      route.vehicleCapacityMax
    );
    if (maxSeats > 0) {
      map.set(routeId, maxSeats);
    }
  });
  return map;
};

export const getItemCapacityNeeded = (item = {}, routeCapacityMap = null) => {
  const direct = toNonNegativeInt(
    item?.capacity_needed ??
    item?.capacityNeeded ??
    item?.passengers_count ??
    item?.num_students
  );
  if (direct > 0) return direct;

  const routeId = String(item?.route_id || item?.id || '').trim();
  if (routeCapacityMap && routeId && routeCapacityMap.has(routeId)) {
    return toNonNegativeInt(routeCapacityMap.get(routeId));
  }

  return getStopsPeakPassengers(item?.stops || []);
};

export const getBusMinSeats = (items = [], routeCapacityMap = null) => {
  if (!Array.isArray(items) || items.length === 0) return 0;
  return items.reduce((maxSeats, item) => {
    const needed = getItemCapacityNeeded(item, routeCapacityMap);
    const fallbackVehicleSeats = toNonNegativeInt(
      item?.vehicle_capacity_max ??
      item?.vehicleCapacityMax
    );
    const seatRequirement = needed > 0 ? needed : fallbackVehicleSeats;
    return seatRequirement > maxSeats ? seatRequirement : maxSeats;
  }, 0);
};
