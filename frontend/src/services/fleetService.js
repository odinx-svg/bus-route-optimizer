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

export const listFleetCompanies = async () => {
  const response = await fetch(`${API_URL}/api/fleet/companies`);
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

export const testTelematicsLink = async (payload) => {
  const response = await fetch(`${API_URL}/api/fleet/telematics/test-link`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
};

export const previewFleetImport = async (file) => {
  const form = new FormData();
  form.append('file', file);
  const response = await fetch(`${API_URL}/api/fleet/import/preview`, {
    method: 'POST',
    body: form,
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
};

export const commitFleetImport = async ({ file, primarySheetName, uteName = '' }) => {
  const form = new FormData();
  form.append('file', file);
  form.append('primary_sheet_name', primarySheetName);
  if (uteName && String(uteName).trim()) {
    form.append('ute_name', String(uteName).trim());
  }
  const response = await fetch(`${API_URL}/api/fleet/import/commit`, {
    method: 'POST',
    body: form,
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
};

export const listUTEs = async ({ activeOnly = true } = {}) => {
  const response = await fetch(`${API_URL}/api/fleet/utes?active_only=${activeOnly ? 'true' : 'false'}`);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
};

export const createUTE = async (payload) => {
  const response = await fetch(`${API_URL}/api/fleet/utes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
};
