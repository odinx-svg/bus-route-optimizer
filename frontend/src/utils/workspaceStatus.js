const READINESS_CONFIG = {
  ready: {
    label: 'Lista para publicar',
    tone: 'ready',
    chipClass: 'border-emerald-500/30 bg-emerald-500/12 text-emerald-200',
  },
  warning: {
    label: 'Requiere revision',
    tone: 'warning',
    chipClass: 'border-amber-500/30 bg-amber-500/12 text-amber-200',
  },
  blocked: {
    label: 'Bloqueada',
    tone: 'blocked',
    chipClass: 'border-rose-500/35 bg-rose-500/14 text-rose-200',
  },
  published: {
    label: 'Publicada',
    tone: 'published',
    chipClass: 'border-cyan-500/35 bg-cyan-500/12 text-cyan-200',
  },
};

const NEXT_ACTION_LABELS = {
  optimize: 'Optimizar',
  review: 'Revisar',
  reconcile: 'Reconciliar flota',
  save: 'Guardar',
  publish: 'Publicar',
  resolve_conflict: 'Revisar conflictos',
};

const BLOCKING_REASON_TEXT = {
  no_schedule: 'Todavia no hay horario listo para operar.',
  fleet_conflict: 'Hay conflicto real de flota con otra publicacion.',
  virtual_reconciliation_required: 'Quedan buses provisionales pendientes de asignar a flota real.',
  workspace_archived: 'La optimizacion esta archivada y fuera de operacion.',
};

export function getWorkspaceReadinessConfig(readinessState = 'warning') {
  return READINESS_CONFIG[readinessState] || READINESS_CONFIG.warning;
}

export function getNextActionLabel(action = 'review') {
  return NEXT_ACTION_LABELS[action] || 'Revisar';
}

export function getBlockingReasonText(reason = '') {
  return BLOCKING_REASON_TEXT[reason] || '';
}

export function getWorkspacePendingLabel(workspace = null) {
  if (!workspace) return 'Sin optimizacion abierta';
  if (workspace.readiness_state === 'blocked') return 'Con conflicto';
  if ((workspace.pending_virtual_count || 0) > 0) return 'Pendiente de reconciliar';
  if (workspace.status === 'active') return 'Publicado';
  if (workspace.readiness_state === 'ready') return 'Lista para publicar';
  return 'Sin publicar';
}

export function getWorkspaceStatusLabel(workspace = null) {
  if (!workspace) return 'Sin optimizacion';
  if (workspace.status === 'active') return 'Publicado';
  if (workspace.status === 'inactive') return 'Archivado';
  return 'Borrador';
}

export function getScopeLabel(scopeSummary = null) {
  if (!scopeSummary || typeof scopeSummary !== 'object') return 'Empresa';
  return String(scopeSummary.label || '').trim() || 'Empresa';
}

export function getPlanningStageLabels(workspace = null) {
  const isPublished = workspace?.status === 'active';
  const hasSchedule = Boolean(workspace?.working_version_id || workspace?.published_version_id);
  const hasPendingVirtual = Number(workspace?.pending_virtual_count || 0) > 0;
  const hasConflict = Number(workspace?.conflict_count || 0) > 0;

  return [
    { key: 'data', label: 'Datos cargados', done: hasSchedule || isPublished, active: !hasSchedule && !isPublished },
    { key: 'optimized', label: 'Optimizacion generada', done: hasSchedule || isPublished, active: hasSchedule && !isPublished },
    { key: 'review', label: 'Revision', done: hasSchedule || isPublished, active: hasSchedule && !isPublished && !hasPendingVirtual && !hasConflict },
    { key: 'reconcile', label: 'Flota reconciliada', done: !hasPendingVirtual && !hasConflict && (hasSchedule || isPublished), active: hasPendingVirtual || hasConflict },
    { key: 'published', label: 'Publicado', done: isPublished, active: isPublished },
  ];
}
