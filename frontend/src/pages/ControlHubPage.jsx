import React, { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, ArchiveRestore, Bus, FolderOpen, Plus, RefreshCw, Trash2, X } from 'lucide-react';
import { fetchFleetVehicles } from '../services/fleetService';
import { notifications } from '../services/notifications';

const STATUS_LABEL = {
  active: { text: 'Activa', cls: 'text-emerald-300 border-emerald-500/35 bg-emerald-500/10' },
  draft: { text: 'Borrador', cls: 'text-amber-300 border-amber-500/35 bg-amber-500/10' },
  inactive: { text: 'Inactiva', cls: 'text-slate-300 border-slate-500/35 bg-slate-500/10' },
};

export default function ControlHubPage({
  workspaces = [],
  activeWorkspaceId = null,
  onOpenWorkspace,
  onCreateWorkspace,
  onRefresh,
  onArchiveWorkspace,
  onRestoreWorkspace,
  onDeleteWorkspace,
}) {
  const [fleetSummary, setFleetSummary] = useState(null);
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
    return () => { cancelled = true; };
  }, []);

  const metrics = useMemo(() => {
    const total = workspaces.length;
    const active = workspaces.filter((ws) => ws.status === 'active').length;
    const drafts = workspaces.filter((ws) => ws.status === 'draft').length;
    const inactive = workspaces.filter((ws) => ws.status === 'inactive').length;
    return { total, active, drafts, inactive };
  }, [workspaces]);

  const expectedDeleteName = String(deleteDialog.workspace?.name || '');
  const canConfirmDelete = expectedDeleteName.length > 0 && deleteDialog.typedName.trim() === expectedDeleteName;

  const openDeleteDialog = (workspace) => {
    setDeleteDialog({
      open: true,
      workspace,
      typedName: '',
    });
  };

  const closeDeleteDialog = () => {
    if (deletingWorkspaceId) return;
    setDeleteDialog({
      open: false,
      workspace: null,
      typedName: '',
    });
  };

  const handleConfirmDelete = async () => {
    const target = deleteDialog.workspace;
    if (!target || !canConfirmDelete || deletingWorkspaceId) return;
    setDeletingWorkspaceId(String(target.id));
    try {
      await onDeleteWorkspace?.(target.id, expectedDeleteName);
      notifications.success('Optimizacion eliminada', `${expectedDeleteName} se borro de forma permanente`);
      setDeleteDialog({
        open: false,
        workspace: null,
        typedName: '',
      });
    } catch (error) {
      notifications.error('No se pudo borrar', error?.message || 'Error al eliminar la optimizacion');
    } finally {
      setDeletingWorkspaceId(null);
    }
  };

  return (
    <div className="h-full w-full overflow-auto control-panel rounded-[16px] p-4 md:p-5 space-y-4">
      <div className="flex items-end justify-between border-b border-[#2a4056] pb-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-cyan-300/90 data-mono">Control Hub</p>
          <h2 className="text-[22px] font-semibold text-[#ecf4fb] mt-1" style={{ fontFamily: 'Sora, IBM Plex Sans, Segoe UI, sans-serif' }}>
            Optimizaciones Guardadas
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onRefresh}
            className="px-2.5 py-1.5 control-btn rounded-md text-[11px] font-semibold uppercase tracking-[0.08em] flex items-center gap-1"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refrescar
          </button>
          <button
            onClick={onCreateWorkspace}
            className="px-2.5 py-1.5 control-btn-primary rounded-md text-[11px] font-semibold uppercase tracking-[0.08em] flex items-center gap-1"
          >
            <Plus className="w-3.5 h-3.5" />
            Nueva
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        <div className="control-card rounded-[14px] p-3.5 border border-[#304a62]">
          <p className="text-[10px] uppercase tracking-[0.12em] text-slate-400">Total</p>
          <p className="text-[24px] font-semibold data-mono text-slate-100 mt-1">{metrics.total}</p>
        </div>
        <div className="control-card rounded-[14px] p-3.5 border border-[#304a62]">
          <p className="text-[10px] uppercase tracking-[0.12em] text-slate-400">Activas</p>
          <p className="text-[24px] font-semibold data-mono text-emerald-300 mt-1">{metrics.active}</p>
        </div>
        <div className="control-card rounded-[14px] p-3.5 border border-[#304a62]">
          <p className="text-[10px] uppercase tracking-[0.12em] text-slate-400">Borradores</p>
          <p className="text-[24px] font-semibold data-mono text-amber-300 mt-1">{metrics.drafts}</p>
        </div>
        <div className="control-card rounded-[14px] p-3.5 border border-[#304a62]">
          <p className="text-[10px] uppercase tracking-[0.12em] text-slate-400">Flota Activa</p>
          <p className="text-[24px] font-semibold data-mono text-cyan-300 mt-1">{fleetSummary?.active ?? 0}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3">
        {workspaces.length === 0 && (
          <div className="control-card rounded-[14px] p-6 border border-[#304a62] text-center text-slate-400">
            No hay optimizaciones creadas todavia
          </div>
        )}
        {workspaces.map((workspace) => {
          const statusCfg = STATUS_LABEL[workspace.status] || STATUS_LABEL.draft;
          const selected = String(workspace.id) === String(activeWorkspaceId);
          const buses = workspace?.summary_metrics?.best_buses ?? workspace?.summary_metrics?.total_buses ?? 0;
          const infeasible = workspace?.summary_metrics?.infeasible_buses ?? 0;
          const loadMin = workspace?.summary_metrics?.min_routes_per_bus;
          const loadMax = workspace?.summary_metrics?.max_routes_per_bus;
          const loadMedian = workspace?.summary_metrics?.median_routes_per_bus;
          const loadSpread = workspace?.summary_metrics?.load_spread_routes;
          return (
            <div
              key={workspace.id}
              className={`control-card rounded-[14px] p-4 border transition-colors ${selected ? 'border-cyan-400/55' : 'border-[#304a62]'}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[15px] font-semibold text-slate-100">{workspace.name}</p>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    {workspace.city_label || 'Sin ciudad'} | v{workspace.working_version_number || 0}
                  </p>
                </div>
                <span className={`px-2 py-0.5 rounded-sm border text-[10px] data-mono uppercase tracking-[0.1em] ${statusCfg.cls}`}>
                  {statusCfg.text}
                </span>
              </div>
              <div className="mt-3 flex items-center gap-4 text-[11px] text-slate-300">
                <span className="flex items-center gap-1">
                  <Bus className="w-3.5 h-3.5" />
                  {buses} buses
                </span>
                <span className="flex items-center gap-1">
                  <Activity className="w-3.5 h-3.5" />
                  {infeasible} inviables
                </span>
                {(Number.isFinite(loadMin) && Number.isFinite(loadMax)) ? (
                  <span className="data-mono">
                    carga {loadMin}-{loadMax}
                  </span>
                ) : null}
                {(Number.isFinite(loadMedian) || Number.isFinite(loadSpread)) ? (
                  <span className={`data-mono ${Number(loadSpread || 0) > 2 ? 'text-rose-300' : 'text-emerald-300'}`}>
                    med {loadMedian ?? 0} | spread {loadSpread ?? 0}
                  </span>
                ) : null}
                <span>{new Date(workspace.updated_at).toLocaleString()}</span>
              </div>
              <div className="mt-3 flex items-center gap-2">
                <button
                  onClick={() => onOpenWorkspace?.(workspace.id)}
                  className="px-2.5 py-1.5 control-btn rounded-md text-[11px] font-semibold uppercase tracking-[0.08em] flex items-center gap-1"
                >
                  <FolderOpen className="w-3.5 h-3.5" />
                  Abrir Studio
                </button>
                {workspace.status !== 'inactive' ? (
                  <button
                    onClick={() => onArchiveWorkspace?.(workspace.id)}
                    className="px-2.5 py-1.5 rounded-md text-[11px] border border-slate-500/35 text-slate-300 hover:bg-slate-500/10"
                  >
                    Archivar
                  </button>
                ) : (
                  <button
                    onClick={() => onRestoreWorkspace?.(workspace.id)}
                    className="px-2.5 py-1.5 rounded-md text-[11px] border border-cyan-500/35 text-cyan-300 hover:bg-cyan-500/10 flex items-center gap-1"
                  >
                    <ArchiveRestore className="w-3.5 h-3.5" />
                    Restaurar
                  </button>
                )}
                <button
                  onClick={() => openDeleteDialog(workspace)}
                  className="px-2.5 py-1.5 rounded-md text-[11px] border border-rose-500/40 text-rose-300 hover:bg-rose-500/10 flex items-center gap-1"
                  title="Borrar optimizacion de forma permanente"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Borrar
                </button>
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
