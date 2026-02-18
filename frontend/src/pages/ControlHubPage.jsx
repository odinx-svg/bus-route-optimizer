import React, { useEffect, useMemo, useState } from 'react';
import { Activity, ArchiveRestore, Bus, FolderOpen, Plus, RefreshCw } from 'lucide-react';
import { fetchFleetVehicles } from '../services/fleetService';

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
}) {
  const [fleetSummary, setFleetSummary] = useState(null);

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
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
