const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function parseResponse(response) {
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data?.detail || data?.message || `HTTP ${response.status}`);
  }
  return response.json();
}

export async function listWorkspaces(filters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    params.set(key, String(value));
  });
  const suffix = params.toString() ? `?${params.toString()}` : '';
  const response = await fetch(`${API_BASE_URL}/api/workspaces${suffix}`);
  return parseResponse(response);
}

export async function createWorkspace(payload) {
  const response = await fetch(`${API_BASE_URL}/api/workspaces`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  });
  return parseResponse(response);
}

export async function getWorkspace(workspaceId) {
  const response = await fetch(`${API_BASE_URL}/api/workspaces/${workspaceId}`);
  return parseResponse(response);
}

export async function getWorkspaceVersions(workspaceId) {
  const response = await fetch(`${API_BASE_URL}/api/workspaces/${workspaceId}/versions`);
  return parseResponse(response);
}

export async function getWorkspaceVersion(workspaceId, versionId) {
  const response = await fetch(`${API_BASE_URL}/api/workspaces/${workspaceId}/versions/${versionId}`);
  return parseResponse(response);
}

export async function saveWorkspaceVersion(workspaceId, payload = {}) {
  const response = await fetch(`${API_BASE_URL}/api/workspaces/${workspaceId}/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return parseResponse(response);
}

export async function publishWorkspaceVersion(workspaceId, payload = {}) {
  const response = await fetch(`${API_BASE_URL}/api/workspaces/${workspaceId}/publish`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return parseResponse(response);
}

export async function renameWorkspace(workspaceId, name) {
  const response = await fetch(`${API_BASE_URL}/api/workspaces/${workspaceId}/rename`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  return parseResponse(response);
}

export async function archiveWorkspace(workspaceId) {
  const response = await fetch(`${API_BASE_URL}/api/workspaces/${workspaceId}/archive`, {
    method: 'POST',
  });
  return parseResponse(response);
}

export async function restoreWorkspace(workspaceId) {
  const response = await fetch(`${API_BASE_URL}/api/workspaces/${workspaceId}/restore`, {
    method: 'POST',
  });
  return parseResponse(response);
}

export async function deleteWorkspace(workspaceId, confirmName) {
  const response = await fetch(`${API_BASE_URL}/api/workspaces/${workspaceId}/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirm_name: confirmName }),
  });
  return parseResponse(response);
}

export async function migrateLegacyWorkspaces() {
  const response = await fetch(`${API_BASE_URL}/api/workspaces/migrate-legacy`, {
    method: 'POST',
  });
  return parseResponse(response);
}

export async function getWorkspacePreferences() {
  const response = await fetch(`${API_BASE_URL}/api/workspaces/preferences`);
  return parseResponse(response);
}

export async function setLastOpenWorkspace(workspaceId) {
  const response = await fetch(`${API_BASE_URL}/api/workspaces/preferences/last-open`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ workspace_id: workspaceId }),
  });
  return parseResponse(response);
}

export async function optimizeWorkspacePipeline(workspaceId, payload) {
  const response = await fetch(`${API_BASE_URL}/api/workspaces/${workspaceId}/optimize-pipeline`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return parseResponse(response);
}

export async function getWorkspaceOptimizationOptions(workspaceId) {
  const response = await fetch(`${API_BASE_URL}/api/workspaces/${workspaceId}/optimization-options`);
  return parseResponse(response);
}

export async function setWorkspaceOptimizationOptions(workspaceId, payload = {}) {
  const response = await fetch(`${API_BASE_URL}/api/workspaces/${workspaceId}/optimization-options`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return parseResponse(response);
}
