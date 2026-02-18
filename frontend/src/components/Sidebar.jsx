import React from 'react';
import { Upload, Play, RotateCcw, Clock } from 'lucide-react';
import FileUpload from './FileUpload';

const DAY_LABELS = { L: 'Lun', M: 'Mar', Mc: 'Mié', X: 'Jue', V: 'Vie' };

const Sidebar = ({
  activeTab,
  setActiveTab,
  onUploadSuccess,
  routes = [],
  parseReport = null,
  schedule = [],
  onOptimize,
  isOptimizing,
  onReset,
  optimizationStats = null,
  scheduleByDay = null,
  forceUploadMode = false,
  showCloseButton = false,
  onClose = null,
  children // Para mostrar OptimizationProgress
}) => {
  const hasData = !forceUploadMode && routes.length > 0;
  const hasResults = schedule.length > 0;
  const droppedRows = Number(parseReport?.rows_dropped_invalid || 0);
  const invalidReasons = Array.isArray(parseReport?.invalid_reasons) ? parseReport.invalid_reasons : [];

  return (
    <aside className="w-[300px] control-panel rounded-[12px] flex flex-col flex-shrink-0 overflow-hidden">
      {/* Header */}
      <div className="px-5 pt-5 pb-4 border-b border-[#243649]">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-[11px] font-semibold text-[#d6e6f2] uppercase tracking-[0.14em]">Ingesta</p>
            <p className="text-[11px] text-slate-500 mt-0.5">Carga de datasets operativos</p>
          </div>
          {showCloseButton && typeof onClose === 'function' && (
            <button
              type="button"
              onClick={onClose}
              className="px-2 py-1 text-[10px] uppercase tracking-[0.08em] rounded-md border border-[#2b4257] text-slate-400 hover:text-slate-200 hover:bg-[#152230]"
            >
              Cerrar
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 pb-4">
        <div className="space-y-4">
          {!hasData ? (
            <div className="animate-fadeIn">
              <FileUpload onUploadSuccess={onUploadSuccess} />
            </div>
          ) : (
            <div className="space-y-3 animate-fadeIn">
              {/* Data summary */}
              <div className="control-card rounded-[10px] p-4">
                <p className="text-[10px] font-medium text-slate-500 uppercase tracking-[0.14em] mb-3">Datos cargados</p>
                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-[#111c28] border border-[#2b4257] rounded-[8px] p-3 text-center">
                    <p className="text-xl font-semibold text-[#eef6fc] data-mono">{routes.length}</p>
                    <p className="text-[10px] text-slate-500 mt-0.5 uppercase tracking-[0.1em]">Rutas</p>
                  </div>
                  <div className="bg-[#111c28] border border-[#2b4257] rounded-[8px] p-3 text-center">
                    <p className="text-xl font-semibold text-cyan-300 data-mono">
                      {routes.filter(r => r.type === 'entry').length}
                    </p>
                    <p className="text-[10px] text-slate-500 mt-0.5 uppercase tracking-[0.1em]">Entradas</p>
                  </div>
                  <div className="bg-[#111c28] border border-[#2b4257] rounded-[8px] p-3 text-center">
                    <p className="text-xl font-semibold text-amber-300 data-mono">
                      {routes.filter(r => r.type === 'exit').length}
                    </p>
                    <p className="text-[10px] text-slate-500 mt-0.5 uppercase tracking-[0.1em]">Salidas</p>
                  </div>
                  <div className="bg-[#111c28] border border-[#2b4257] rounded-[8px] p-3 text-center">
                    <p className="text-xl font-semibold text-[#eef6fc] data-mono">
                      {new Set(routes.map(r => r.school_name)).size}
                    </p>
                    <p className="text-[10px] text-slate-500 mt-0.5 uppercase tracking-[0.1em]">Colegios</p>
                  </div>
                </div>
              </div>

              {parseReport && (
                <div className={`control-card rounded-[10px] p-4 border ${droppedRows > 0 ? 'border-amber-500/35' : 'border-[#2b4257]'}`}>
                  <p className="text-[10px] font-medium text-slate-500 uppercase tracking-[0.14em] mb-2">Calidad de datos</p>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-[#111c28] border border-[#2b4257] rounded-[8px] p-2.5 text-center">
                      <p className="text-lg font-semibold text-[#eef6fc] data-mono">{parseReport.rows_total || 0}</p>
                      <p className="text-[9px] text-slate-500 uppercase tracking-[0.1em]">Filas</p>
                    </div>
                    <div className={`bg-[#111c28] border rounded-[8px] p-2.5 text-center ${droppedRows > 0 ? 'border-amber-500/40' : 'border-[#2b4257]'}`}>
                      <p className={`text-lg font-semibold data-mono ${droppedRows > 0 ? 'text-amber-300' : 'text-emerald-300'}`}>
                        {droppedRows}
                      </p>
                      <p className="text-[9px] text-slate-500 uppercase tracking-[0.1em]">Descartadas</p>
                    </div>
                  </div>
                  {invalidReasons.length > 0 && (
                    <div className="mt-2 max-h-24 overflow-y-auto space-y-1">
                      {invalidReasons.slice(0, 6).map((item) => (
                        <div key={`${item.reason}-${item.count}`} className="flex items-center justify-between text-[10px] data-mono bg-[#111c28] border border-[#2b4257] rounded px-2 py-1">
                          <span className="text-slate-400 truncate pr-2">{item.reason}</span>
                          <span className="text-amber-300">{item.count}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Progress UI (OptimizationProgress component) */}
              {children}

              {!hasResults ? (
                <div className="space-y-2">
                  <button
                    onClick={onOptimize}
                    disabled={isOptimizing}
                    className="w-full py-3 control-btn-primary disabled:opacity-40 disabled:cursor-not-allowed rounded-[8px] font-semibold flex items-center justify-center gap-2 transition-colors text-[12px] uppercase tracking-[0.12em]"
                  >
                    {isOptimizing ? (
                      <span className="animate-pulse">Optimizando...</span>
                    ) : (
                      <>
                        <Play size={13} fill="currentColor" />
                        Ejecutar Pipeline
                      </>
                    )}
                  </button>
                  <button
                    onClick={onReset}
                    className="w-full py-2 text-[11px] text-slate-500 hover:text-rose-300 transition-colors flex items-center justify-center gap-1.5"
                  >
                    <RotateCcw size={11} />
                    Reset datos
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Results */}
                  {optimizationStats && (
                    <div className="control-card rounded-[10px] p-4">
                      <p className="text-[10px] font-medium text-cyan-300 uppercase tracking-[0.14em] mb-3">
                        Resultados
                      </p>
                      <div className="grid grid-cols-2 gap-2">
                        <div className="bg-[#111c28] rounded-[8px] p-3 text-center border border-[#2b4257]">
                          <p className="text-2xl font-semibold text-cyan-300 data-mono">
                            {optimizationStats.total_buses}
                          </p>
                          <p className="text-[10px] text-slate-500 mt-0.5 uppercase tracking-[0.1em]">Buses</p>
                        </div>
                        <div className="bg-[#111c28] rounded-[8px] p-3 text-center border border-[#2b4257]">
                          <p className="text-2xl font-semibold text-[#eef6fc] data-mono">
                            {optimizationStats.avg_routes_per_bus || 0}
                          </p>
                          <p className="text-[10px] text-slate-500 mt-0.5 uppercase tracking-[0.1em]">Media/Bus</p>
                        </div>
                        <div className="bg-[#111c28] rounded-[8px] p-3 text-center border border-[#2b4257]">
                          <p className="text-lg font-semibold text-cyan-300 data-mono">
                            {optimizationStats.total_entries || 0}
                          </p>
                          <p className="text-[10px] text-slate-500 mt-0.5 uppercase tracking-[0.1em]">Entradas</p>
                        </div>
                        <div className="bg-[#111c28] rounded-[8px] p-3 text-center border border-[#2b4257]">
                          <p className="text-lg font-semibold text-amber-300 data-mono">
                            {optimizationStats.total_exits || 0}
                          </p>
                          <p className="text-[10px] text-slate-500 mt-0.5 uppercase tracking-[0.1em]">Salidas</p>
                        </div>
                        {optimizationStats.buses_with_both > 0 && (
                          <div className="col-span-2 bg-[#111c28] rounded-[8px] p-2.5 text-center border border-[#2b4257]">
                            <span className="text-[13px] font-semibold text-slate-200 data-mono">
                              {optimizationStats.buses_with_both}
                            </span>
                            <span className="text-[10px] text-slate-500 ml-2 uppercase tracking-[0.1em]">buses mixtos</span>
                          </div>
                        )}
                      </div>
                      {optimizationStats.total_early_shift_minutes > 0 && (
                        <div className="mt-2.5 flex items-center gap-1.5 text-[10px] text-slate-500 data-mono">
                          <Clock size={10} />
                          <span>
                            Adelanto total: {optimizationStats.total_early_shift_minutes} min
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Per-day summary */}
                  {scheduleByDay && (
                    <div className="control-card rounded-[10px] p-4">
                      <p className="text-[10px] font-medium text-slate-500 uppercase tracking-[0.14em] mb-2">Horario por día</p>
                      <div className="space-y-1">
                        {['L', 'M', 'Mc', 'X', 'V'].map(day => {
                          const dayData = scheduleByDay[day];
                          const buses = dayData?.stats?.total_buses || 0;
                          const entries = dayData?.stats?.total_entries || 0;
                          const exits = dayData?.stats?.total_exits || 0;
                          const totalRoutes = entries + exits;
                          return (
                            <div key={day} className="flex items-center justify-between py-1">
                              <span className="text-[11px] text-slate-400 w-8 data-mono">{DAY_LABELS[day]}</span>
                              <div className="flex items-center gap-2">
                                <span className="text-[9px] text-cyan-300/70 data-mono">{entries}E</span>
                                <span className="text-[9px] text-amber-300/70 data-mono">{exits}S</span>
                                <span className="text-[10px] text-slate-600 data-mono w-10 text-right">{totalRoutes}r</span>
                                <span className="text-[12px] font-semibold text-[#eef6fc] data-mono w-6 text-right">{buses}</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  <button
                    onClick={onReset}
                    className="w-full py-2.5 control-btn rounded-[8px] text-[11px] font-semibold uppercase tracking-[0.1em] flex items-center justify-center gap-1.5"
                  >
                    <RotateCcw size={12} />
                    Nueva corrida
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
