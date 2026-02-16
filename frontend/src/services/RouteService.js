import L from 'leaflet';

const OSRM_API_URL = import.meta.env.VITE_OSRM_URL || 'http://187.77.33.218:5000/route/v1/driving';

// In-memory geometry cache: routeId -> positions[]
// Routes repeat across days, so caching avoids redundant OSRM calls
const geometryCache = new Map();

const isFiniteCoordinate = (lat, lon) => {
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return false;
    if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return false;
    if (Math.abs(lat) < 1e-9 && Math.abs(lon) < 1e-9) return false;
    return true;
};

const toNumber = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : NaN;
};

const normalizeStopsForGeometry = (stops = []) => {
    const prepared = (Array.isArray(stops) ? stops : [])
        .map((stop, index) => ({
            lat: toNumber(stop?.lat),
            lon: toNumber(stop?.lon ?? stop?.lng),
            order: Number.isFinite(Number(stop?.order)) ? Number(stop?.order) : Number.POSITIVE_INFINITY,
            timeFromStart: Number.isFinite(Number(stop?.time_from_start ?? stop?.timeFromStart))
                ? Number(stop?.time_from_start ?? stop?.timeFromStart)
                : Number.POSITIVE_INFINITY,
            index,
        }))
        .filter((stop) => isFiniteCoordinate(stop.lat, stop.lon))
        .sort((a, b) => {
            if (a.order !== b.order) return a.order - b.order;
            if (a.timeFromStart !== b.timeFromStart) return a.timeFromStart - b.timeFromStart;
            return a.index - b.index;
        });

    const unique = [];
    for (const stop of prepared) {
        const prev = unique[unique.length - 1];
        if (prev && Math.abs(prev.lat - stop.lat) < 1e-6 && Math.abs(prev.lon - stop.lon) < 1e-6) {
            continue;
        }
        unique.push({ lat: stop.lat, lon: stop.lon });
    }
    return unique;
};

const buildStopsSignature = (stops = []) => (
    stops.map((s) => `${s.lat.toFixed(6)},${s.lon.toFixed(6)}`).join('|')
);

/**
 * Check if a route's geometry is already cached.
 */
export const isGeometryCached = (routeId, stops = null) => {
    if (!routeId || !geometryCache.has(routeId)) {
        return false;
    }
    const cached = geometryCache.get(routeId);
    if (Array.isArray(cached)) {
        return cached.length > 1;
    }
    if (!cached || !Array.isArray(cached.positions)) {
        return false;
    }
    if (!stops || !Array.isArray(stops) || stops.length < 2) {
        return cached.positions.length > 1;
    }
    const normalizedStops = normalizeStopsForGeometry(stops);
    if (normalizedStops.length < 2) {
        return false;
    }
    const signature = buildStopsSignature(normalizedStops);
    return cached.signature === signature && cached.positions.length > 1;
};

/**
 * Clear the geometry cache (e.g., on reset/new upload).
 */
export const clearGeometryCache = () => {
  geometryCache.clear();
};

/**
 * Fetches the route geometry (polyline) for a given set of stops.
 * Uses an in-memory cache keyed by routeId to avoid redundant OSRM calls.
 * @param {Array<{lat: number, lon: number}>} stops - List of stops (lat, lon).
 * @param {string} [routeId] - Optional route ID for caching.
 * @returns {Promise<Array<[number, number]>>} - List of [lat, lon] points for the polyline.
 */
export const fetchRouteGeometry = async (stops, routeId) => {
    const normalizedStops = normalizeStopsForGeometry(stops);
    const signature = buildStopsSignature(normalizedStops);

    // Return cached geometry if available
    if (routeId && geometryCache.has(routeId)) {
        const cached = geometryCache.get(routeId);
        if (Array.isArray(cached)) {
            return cached;
        }
        if (cached?.signature === signature && Array.isArray(cached?.positions)) {
            return cached.positions;
        }
    }

    if (normalizedStops.length < 2) {
        return [];
    }

    // Format coordinates for OSRM: lon,lat;lon,lat...
    const coordinates = normalizedStops.map((s) => `${s.lon},${s.lat}`).join(';');

    try {
        const response = await fetch(`${OSRM_API_URL}/${coordinates}?overview=full&geometries=geojson`);

        if (!response.ok) {
            throw new Error('Failed to fetch route from OSRM');
        }

        const data = await response.json();

        if (data.code !== 'Ok' || !data.routes || data.routes.length === 0) {
            return [];
        }

        // OSRM returns [lon, lat], Leaflet needs [lat, lon]
        const coordinatesGeoJSON = data.routes[0].geometry.coordinates;
        const positions = coordinatesGeoJSON.map(coord => [coord[1], coord[0]]);

        // Cache the result
        if (routeId) {
            geometryCache.set(routeId, { signature, positions });
        }

        return positions;

    } catch (error) {
        console.error("Error fetching route geometry:", error);
        // Fallback to straight lines if API fails
        const positions = normalizedStops.map((s) => [s.lat, s.lon]);
        if (routeId) {
            geometryCache.set(routeId, { signature, positions });
        }
        return positions;
    }
};

/**
 * Fetch positioning (deadhead) geometry between two points.
 * Reuses route geometry fetch + cache using a dedicated connection key.
 *
 * @param {{lat:number, lon?:number, lng?:number}} fromPoint
 * @param {{lat:number, lon?:number, lng?:number}} toPoint
 * @param {string} [cacheKey]
 * @returns {Promise<Array<[number, number]>>}
 */
export const fetchConnectionGeometry = async (fromPoint, toPoint, cacheKey) => {
    const fromLat = Number(fromPoint?.lat);
    const fromLon = Number(fromPoint?.lon ?? fromPoint?.lng);
    const toLat = Number(toPoint?.lat);
    const toLon = Number(toPoint?.lon ?? toPoint?.lng);

    if (![fromLat, fromLon, toLat, toLon].every(Number.isFinite)) {
        return [];
    }

    const key = cacheKey || `conn:${fromLat.toFixed(6)},${fromLon.toFixed(6)}->${toLat.toFixed(6)},${toLon.toFixed(6)}`;
    return fetchRouteGeometry(
        [
            { lat: fromLat, lon: fromLon },
            { lat: toLat, lon: toLon },
        ],
        key,
    );
};
