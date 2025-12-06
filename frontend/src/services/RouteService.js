import L from 'leaflet';

const OSRM_API_URL = 'https://router.project-osrm.org/route/v1/driving';

/**
 * Fetches the route geometry (polyline) for a given set of stops.
 * @param {Array<{lat: number, lon: number}>} stops - List of stops (lat, lon).
 * @returns {Promise<Array<[number, number]>>} - List of [lat, lon] points for the polyline.
 */
export const fetchRouteGeometry = async (stops) => {
    if (!stops || stops.length < 2) {
        return [];
    }

    // Format coordinates for OSRM: lon,lat;lon,lat...
    const coordinates = stops.map(s => `${s.lon},${s.lat}`).join(';');

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
        return coordinatesGeoJSON.map(coord => [coord[1], coord[0]]);

    } catch (error) {
        console.error("Error fetching route geometry:", error);
        // Fallback to straight lines if API fails
        return stops.map(s => [s.lat, s.lon]);
    }
};
