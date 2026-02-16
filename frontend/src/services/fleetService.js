const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const parseError = async (response) => {
  let payload = {};
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }
  return payload?.detail || payload?.message || `Error ${response.status}`;
};

export const fetchFleetVehicles = async () => {
  const response = await fetch(`${API_URL}/api/fleet/vehicles`);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
};

export const createFleetVehicle = async (payload) => {
  const response = await fetch(`${API_URL}/api/fleet/vehicles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
};

export const updateFleetVehicle = async (vehicleId, payload) => {
  const response = await fetch(`${API_URL}/api/fleet/vehicles/${encodeURIComponent(vehicleId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
};

export const deleteFleetVehicle = async (vehicleId) => {
  const response = await fetch(`${API_URL}/api/fleet/vehicles/${encodeURIComponent(vehicleId)}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
};

