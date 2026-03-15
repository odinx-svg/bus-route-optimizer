import React, { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  ArchiveRestore,
  Bus,
  CheckCircle2,
  FolderOpen,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  X,
} from 'lucide-react';
import { fetchFleetVehicles } from '../services/fleetService';
import { notifications } from '../services/notifications';
import {
  getBlockingReasonText,
  getNextActionLabel,
  getScopeLabel,
  getWorkspacePendingLabel,
  getWorkspaceReadinessConfig,
  getWorkspaceStatusLabel,
} from '../utils/workspaceStatus';

const FILTERS = [
  { id: 'all', label: 'Todas' },
  { id: 'draft', label: 'Borrador' },
  { id: 'ready', label: 'Listas para publicar' },
  { id: 'blocked', label: 'Con conflicto' },
  { id: 'active', label: 'Publicadas' },
  { id: 'inactive', label: 'Archivadas' },
];

export default function ControlHubPage({
  workspaces = [],
  activeWorkspaceId = null,
  onOpenWorkspace,
  onCreateWorkspace,
  onRefresh,
  onArchiveWorkspace,
  onRestoreWorkspace,
  onDeleteWorkspace,
  onConfigureWorkspaceOptions,
}) {
  const [fleetSummary, setFleetSummary] = useState(null);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [menuWorkspaceId, setMenuWorkspaceId] = useState(null);
  const [deleteDialog, setDeleteDialog] = useState({
    open: false,
    workspace: null,
    typedName: '',
  });
  const [deletingWorkspaceId, setDeletingWorkspaceId] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const loadFleetSummary = async () => {
      try {
        const data = await fetchFleetVehicles();
        if (!cancelled) setFleetSummary(data?.summary || null);
      } catch {
        if (!cancelled) setFleetSummary(null);
      }
    };
    loadFleetSummary();
    return () => {
      cancelled = true;
    };
  }, []);

  const workspaceMetrics = useMemo(() => {
    const total = workspaces.length;
    const published = workspaces.filter((ws) => ws.status === 'active').length;
    const drafts = workspaces.filter((ws) => ws.status === 'draft').length;
    const blocked = workspaces.filter((ws) => ws.readiness_state === 'blocked').length;
    const pendingReconciliation = workspaces.filter((ws) => Number(ws.pending_virtual_count || 0) > 0).length;
    return { total, published, drafts, blocked, pendingReconciliation };
  }, [workspaces]);

  const filteredWorkspaces = useMemo(() => {
    const normalizedQuery = String(query || '').trim().toLowerCase();
    return workspaces.filter((workspace) => {
      if (filter === 'draft' && workspace.status !== 'draft') return false;
      if (filter === 'ready' && workspace.readiness_state !== 'ready') return false;
      if (filter === 'blocked' && workspace.readiness_state !== 'blocked') return false;
      if (filter === 'active' && workspace.status !== 'active') return false;
      if (filter === 'inactive' && workspace.status !== 'inactive') return false;

      if (!normalizedQuery) return true;
      const haystack = [
        workspace.name,
        workspace.city_label,
        workspace.scope_summary?.label,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }, [filter, query, workspaces]);

  const pendingToday = useMemo(() => ({
    unpublished: workspaces.filter((ws) => ws.status === 'draft').length,
    provisional: workspaces.filter((ws) => Number(ws.pending_virtual_count || 0) > 0).length,
    blocked: workspaces.filter((ws) => Number(ws.conflict_count || 0) > 0 || ws.readiness_state === 'blocked').length,
  }), [workspaces]);

  const expectedDeleteName = String(deleteDialog.workspace?.name || '');
  const canConfirmDelete = expectedDeleteName.length > 0 && deleteDialog.typedName.trim() === expectedDeleteName;

  const closeDeleteDialog = () => {
    if (deletingWorkspaceId) return;
    setDeleteDialog({ open: false, workspace: null, typedName: '' });
  };

  const handleConfirmDelete = async () => {
    const target = deleteDialog.workspace;
    if (!target || !canConfirmDelete || deletingWorkspaceId) return;
    setDeletingWorkspaceId(String(target.id));
    try {
      await onDeleteWorkspace?.(target.id, expectedDeleteName);
      notifications.success('Optimizacion eliminada', `${expectedDeleteName} se borro de forma permanente`);
      setDeleteDialog({ open: false, workspace: null, typedName: '' });
    } catch (error) {
      notifications.error('No se pudo borrar', error?.message || 'Error al eliminar la optimizacion');
    } finally {
      setDeletingWorkspaceId(null);
    }
  };

  const openDeleteDialog = (workspace) => {
    setDeleteDialog({ open: true, workspace, typedName: '' });
    setMenuWorkspaceId(null);
  };

  return (
    <div className="h-full w-full overflow-auto rounded-[18px] control-panel p-4 md:p-5 space-y-4">
      <div className="rounded-[18px] border border-[#304a62] bg-[#0d1623]/95 p-4">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-[11px] uppercase tracking-[0.16em] text-cyan-300/90 data-mono">Panel operativo</p>
            <h2 className="mt-1 text-[24px] font-semibold text-[#ecf4fb]" style={{ fontFamily: 'Sora, IBM Plex Sans, Segoe UI, sans-serif' }}>
              Centro de optimizaciones
            </h2>
            <p className="mt-1 text-[12px] text-slate-400">
              Revisa el estado de cada planificacion, detecta bloqueos y entra directo en el siguiente paso.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onRefresh}
              className="px-2.5 py-1.5 control-btn rounded-md text-[11px] font-semibold uppercase tracking-[0.08em] flex items-center gap-1"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Actualizar
            </button>
            <button
              onClick={onCreateWorkspace}
              className="px-3 py-1.5 control-btn-primary rounded-md text-[11px] font-semibold uppercase tracking-[0.08em] flex items-center gap-1"
            >
              <Plus className="w-3.5 h-3.5" />
              Nueva optimizacion
            </button>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-[1fr_320px]">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <div className="rounded-[14px] border border-[#304a62] bg-[#0b141f] p-3">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-400">Total</p>
              <p className="mt-1 text-[24px] font-semibold data-mono text-white">{workspaceMetrics.total}</p>
            </div>
            <div className="rounded-[14px] border border-[#304a62] bg-[#0b141f] p-3">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-400">Publicadas</p>
              <p className="mt-1 text-[24px] font-semibold data-mono text-cyan-300">{workspaceMetrics.published}</p>
            </div>
            <div className="rounded-[14px] border border-[#304a62] bg-[#0b141f] p-3">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-400">Borradores</p>
              <p className="mt-1 text-[24px] font-semibold data-mono text-amber-300">{workspaceMetrics.drafts}</p>
            </div>
            <div className="rounded-[14px] border border-[#304a62] bg-[#0b141f] p-3">
              <p className="text-[10px] uppercase tracking-[0.12em] text-slate-400">Flota activa</p>
              <p className="mt-1 text-[24px] font-semibold data-mono text-emerald-300">{fleetSummary?.active ?? 0}</p>
            </div>
          </div>

          <div className="rounded-[14px] border border-[#304a62] bg-[#0b141f] p-3">
            <p className="text-[10px] uppercase tracking-[0.12em] text-slate-400">Que falta hoy</p>
            <div className="mt-3 space-y-2 text-[12px]">
              <div className="flex items-center justify-between rounded-md border border-white/5 bg-white/[0.03] px-3 py-2">
                <span className="text-slate-300">Sin publicar</span>
                <span className="data-mono text-white">{pendingToday.unpublished}</span>
              </div>
              <div className="flex items-center justify-between rounded-md border border-white/5 bg-white/[0.03] px-3 py-2">
                <span className="text-slate-300">Pendientes de reconciliar</span>
                <span className="data-mono text-amber-200">{pendingToday.provisional}</span>
              </div>
              <div className="flex items-center justify-between rounded-md border border-white/5 bg-white/[0.03] px-3 py-2">
                <span className="text-slate-300">Bloqueadas por conflicto</span>
                <span className="data-mono text-rose-200">{pendingToday.blocked}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-4 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex flex-wrap gap-2">
            {FILTERS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setFilter(item.id)}
                className={`rounded-full border px-3 py-1.5 text-[11px] font-semibold transition ${
                  filter === item.id
                    ? 'border-cyan-400/55 bg-cyan-500/12 text-cyan-100'
                    : 'border-white/10 bg-white/[0.03] text-slate-300 hover:bg-white/[0.05]'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-2 rounded-xl border border-[#304a62] bg-[#09111b] px-3 py-2 text-[12px] text-slate-300 min-w-[280px]">
            <Search className="w-4 h-4 text-slate-500" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Buscar por nombre, ciudad o ambito"
              className="w-full bg-transparent outline-none placeholder:text-slate-500"
            />
          </label>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3">
        {filteredWorkspaces.length === 0 && (
          <div className="rounded-[16px] border border-[#304a62] bg-[#0d1623]/95 p-8 text-center text-slate-400">
            No hay optimizaciones que coincidan con el filtro actual.
          </div>
        )}

        {filteredWorkspaces.map((workspace) => {
          const readiness = getWorkspaceReadinessConfig(workspace.readiness_state);
          const selected = String(workspace.id) === String(activeWorkspaceId);
          const nextActionLabel = getNextActionLabel(workspace.next_recommended_action);
          const scopeLabel = getScopeLabel(workspace.scope_summary);
          const fleetReal = workspace?.summary_metrics?.fleet_real_assigned ?? workspace?.summary_metrics?.fleet_assigned ?? 0;
          const fleetVirtual = workspace?.pending_virtual_count ?? workspace?.summary_metrics?.fleet_virtual_created ?? 0;
          const conflictCount = workspace?.conflict_count ?? 0;
          const helperText = getBlockingReasonText(workspace.blocking_reason) || getWorkspacePendingLabel(workspace);

          return (
            <div
              key={workspace.id}
              className={`rounded-[16px] border bg-[#0d1623]/95 p-4 transition ${
                selected ? 'border-cyan-400/60 shadow-[0_0_0_1px_rgba(34,211,238,0.14)]' : 'border-[#304a62]'
              }`}
            >
              <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-[18px] font-semibold text-slate-100">{workspace.name}</p>
                    <span className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] ${readiness.chipClass}`}>
                      {readiness.label}
                    </span>
                    <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-1 text-[10px] text-slate-200">
                      {getWorkspaceStatusLabel(workspace)}
                    </span>
                  </div>

                  <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
                    <span>{scopeLabel}</span>
                    <span className="text-slate-600">|</span>
                    <span>{workspace.city_label || 'Sin ciudad'}</span>
                    <span className="text-slate-600">|</span>
                    <span>v{workspace.working_version_number || 0}</span>
                    <span className="text-slate-600">|</span>
                    <span>{new Date(workspace.updated_at).toLocaleString()}</span>
                  </div>

                  <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
                    <div className="rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2">
                      <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Flota real</p>
                      <p className="mt-1 text-[16px] data-mono text-cyan-200">{fleetReal}</p>
                    </div>
                    <div className="rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2">
                      <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Provisionales</p>
                      <p className="mt-1 text-[16px] data-mono text-amber-200">{fleetVirtual}</p>
                    </div>
                    <div className="rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2">
                      <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Conflictos</p>
                      <p className="mt-1 text-[16px] data-mono text-rose-200">{conflictCount}</p>
                    </div>
                    <div className="rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2">
                      <p className="text-[10px] uppercase tracking-[0.08em] text-slate-500">Siguiente paso</p>
                      <p className="mt-1 text-[13px] font-semibold text-white">{nextActionLabel}</p>
                    </div>
                  </div>

                  <div className="mt-3 inline-flex items-start gap-2 rounded-xl border border-white/5 bg-white/[0.03] px-3 py-2">
                    {workspace.readiness_state === 'blocked' ? (
                      <AlertTriangle className="mt-0.5 h-4 w-4 text-rose-300" />
                    ) : (
                      <CheckCircle2 className="mt-0.5 h-4 w-4 text-cyan-300" />
                    )}
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.08em] text-slate-500">Estado operativo</p>
                      <p className="mt-0.5 text-[12px] text-slate-200">{helperText}</p>
                    </div>
                  </div>
                </div>

                <div className="flex shrink-0 flex-wrap items-center gap-2">
                  <button
                    onClick={() => onOpenWorkspace?.(workspace.id)}
                    className="px-3 py-1.5 control-btn-primary rounded-md text-[11px] font-semibold uppercase tracking-[0.08em] flex items-center gap-1"
                  >
                    <FolderOpen className="w-3.5 h-3.5" />
                    {workspace.next_recommended_action === 'publish' ? 'Abrir para publicar' : nextActionLabel}
                  </button>
                  <button
                    onClick={() => onConfigureWorkspaceOptions?.(workspace.id, workspace.name)}
                    className="px-2.5 py-1.5 rounded-md text-[11px] border border-cyan-500/35 text-cyan-300 hover:bg-cyan-500/10"
                  >
                    Reglas
                  </button>
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setMenuWorkspaceId((prev) => (prev === workspace.id ? null : workspace.id))}
                      className="rounded-md border border-white/10 px-2.5 py-1.5 text-slate-300 hover:bg-white/[0.05]"
                    >
                      <MoreHorizontal className="h-4 w-4" />
                    </button>
                    {menuWorkspaceId === workspace.id && (
                      <div className="absolute right-0 top-[calc(100%+8px)] z-20 min-w-[180px] rounded-xl border border-[#304a62] bg-[#09111b] p-1.5 shadow-2xl">
                        {workspace.status !== 'inactive' ? (
                          <button
                            type="button"
                            onClick={async () => {
                              setMenuWorkspaceId(null);
                              await onArchiveWorkspace?.(workspace.id);
                            }}
                            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-[12px] text-slate-200 hover:bg-white/[0.05]"
                          >
                            <Activity className="h-4 w-4 text-slate-400" />
                            Archivar
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={async () => {
                              setMenuWorkspaceId(null);
                              await onRestoreWorkspace?.(workspace.id);
                            }}
                            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-[12px] text-cyan-200 hover:bg-white/[0.05]"
                          >
                            <ArchiveRestore className="h-4 w-4 text-cyan-300" />
                            Restaurar
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => openDeleteDialog(workspace)}
                          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-[12px] text-rose-200 hover:bg-rose-500/10"
                        >
                          <Trash2 className="h-4 w-4 text-rose-300" />
                          Borrar definitivamente
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {deleteDialog.open && (
        <div className="fixed inset-0 z-[1100] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-[#020611]/85 backdrop-blur-[2px]" onClick={closeDeleteDialog} />
          <div className="relative w-full max-w-md rounded-xl border border-rose-500/35 bg-[#0b141f] p-4 shadow-2xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.14em] text-rose-300 data-mono">Borrado permanente</p>
                <h3 className="mt-1 text-[16px] font-semibold text-white">Confirmar eliminacion</h3>
              </div>
              <button
                onClick={closeDeleteDialog}
                className="rounded-md border border-slate-600/50 p-1.5 text-slate-400 hover:text-slate-200 hover:bg-white/5"
                aria-label="Cerrar modal"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="mt-3 rounded-md border border-rose-500/25 bg-rose-500/10 px-3 py-2 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-300 mt-0.5" />
              <p className="text-[12px] text-rose-100 leading-relaxed">
                Esta accion elimina la optimizacion y todas sus versiones guardadas. No se puede deshacer.
              </p>
            </div>

            <p className="mt-3 text-[12px] text-slate-300">
              Escribe el nombre exacto para confirmar:
              <span className="ml-1 font-semibold text-white">"{expectedDeleteName}"</span>
            </p>

            <input
              type="text"
              value={deleteDialog.typedName}
              onChange={(event) => setDeleteDialog((prev) => ({ ...prev, typedName: event.target.value }))}
              placeholder={expectedDeleteName}
              autoFocus
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  event.preventDefault();
                  closeDeleteDialog();
                }
                if (event.key === 'Enter') {
                  event.preventDefault();
                  handleConfirmDelete();
                }
              }}
              className="mt-2 w-full rounded-md border border-[#2a4057] bg-[#0a1324] px-3 py-2 text-[13px] text-white outline-none transition focus:border-rose-400/70"
            />

            <div className="mt-4 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={closeDeleteDialog}
                className="rounded-md border border-[#2a4057] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9eb2c8] transition hover:bg-white/5"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                disabled={!canConfirmDelete || Boolean(deletingWorkspaceId)}
                className="rounded-md border border-rose-500/45 bg-rose-500/20 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-rose-100 transition hover:bg-rose-500/30 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {deletingWorkspaceId ? 'Borrando...' : 'Borrar para siempre'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
