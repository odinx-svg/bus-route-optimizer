import React, { useMemo } from 'react';
import { BarChart3, Building2, Bus, Compass, FileText, MapPin, Users } from 'lucide-react';
import { buildRouteCapacityMap } from '../utils/capacity';

const DAY_LABELS = { L: 'Lunes', M: 'Martes', Mc: 'Miercoles', X: 'Jueves', V: 'Viernes' };
const DAYS = ['L', 'M', 'Mc', 'X', 'V'];

const toMinutes = (value) => {
  if (!value) return 0;
  const [h = 0, m = 0] = String(value).split(':').map((v) => Number(v) || 0);
  return (h * 60) + m;
};

const extractZone = (value = '') => {
  const text = String(value || '').trim();
  if (!text) return null;
  const match = text.match(/\(([^)]+)\)/);
  if (match?.[1]) return match[1].trim();
  const firstChunk = text.split(',')[0]?.trim();
  if (!firstChunk) return null;
  const normalized = firstChunk.replace(/\s+/g, ' ').trim();
  if (!normalized) return null;
  return normalized.length > 26 ? `${normalized.slice(0, 26)}...` : normalized;
};

const KpiCard = ({ icon: Icon, label, value, tone = 'text-cyan-300', subtitle = null }) => (
  <div className="control-card rounded-[12px] p-4 border border-[#2f465d]">
    <div className="flex items-center justify-between">
      <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">{label}</p>
      <Icon className="w-4 h-4 text-slate-500" />
    </div>
    <p className={`mt-2 text-[24px] leading-none font-semibold data-mono ${tone}`}>{value}</p>
    {subtitle ? <p className="mt-1.5 text-[10px] text-slate-500">{subtitle}</p> : null}
  </div>
);

const HorizontalBars = ({ title, rows = [], colorClass = 'bg-cyan-400' }) => (
  <div className="control-card rounded-[12px] p-4 border border-[#2f465d]">
    <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500 mb-3">{title}</p>
    <div className="space-y-2.5">
      {rows.length === 0 && (
        <p className="text-[11px] text-slate-500">Sin datos suficientes.</p>
      )}
      {rows.map((row) => (
        <div key={row.name} className="space-y-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] text-slate-300 truncate">{row.name}</span>
            <span className="text-[11px] text-slate-400 data-mono">{row.value}</span>
          </div>
          <div className="h-1.5 rounded-full bg-[#152434] overflow-hidden">
            <div
              className={`h-full ${colorClass}`}
              style={{ width: `${Math.max(4, Math.min(100, row.percent || 0))}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  </div>
);

export default function OperationsDashboard({ routes = [], scheduleByDay = null, activeDay = 'L' }) {
  const data = useMemo(() => {
    const allRoutes = Array.isArray(routes) ? routes : [];
    const capacityMap = buildRouteCapacityMap(allRoutes);

    const schools = new Map();
    const contracts = new Map();
    const zones = new Map();

    let totalStops = 0;
    let totalPeakStudents = 0;
    let maxRouteStudents = 0;

    allRoutes.forEach((route) => {
      if (!route) return;
      const schoolName = String(route.school_name || 'Unknown').trim() || 'Unknown';
      const contractId = String(route.contract_id || 'N/A').trim() || 'N/A';
      const routeId = String(route.id || route.route_id || '').trim();
      const routeStudents = capacityMap.get(routeId) || 0;

      totalStops += Array.isArray(route.stops) ? route.stops.length : 0;
      totalPeakStudents += routeStudents;
      if (routeStudents > maxRouteStudents) maxRouteStudents = routeStudents;

      schools.set(
        schoolName,
        (schools.get(schoolName) || 0) + 1,
      );
      contracts.set(
        contractId,
        (contracts.get(contractId) || 0) + 1,
      );

      const schoolZone = extractZone(route.school_name);
      const firstStopZone = extractZone(route?.stops?.[0]?.name);
      const zone = schoolZone || firstStopZone || 'Sin zona';
      zones.set(zone, (zones.get(zone) || 0) + 1);
    });

    const byDayRows = DAYS.map((day) => {
      const daySchedule = scheduleByDay?.[day]?.schedule || [];
      const buses = daySchedule.length;
      const items = daySchedule.reduce((acc, bus) => acc + (bus?.items?.length || 0), 0);
      const from = daySchedule
        .flatMap((bus) => bus?.items || [])
        .map((i) => toMinutes(i?.start_time))
        .filter((v) => Number.isFinite(v));
      const to = daySchedule
        .flatMap((bus) => bus?.items || [])
        .map((i) => toMinutes(i?.end_time))
        .filter((v) => Number.isFinite(v));
      const span = from.length && to.length ? `${Math.floor(Math.min(...from) / 60)
        .toString()
        .padStart(2, '0')}:${(Math.min(...from) % 60).toString().padStart(2, '0')} - ${Math.floor(Math.max(...to) / 60)
        .toString()
        .padStart(2, '0')}:${(Math.max(...to) % 60).toString().padStart(2, '0')}` : '--';
      return {
        day,
        label: DAY_LABELS[day],
        buses,
        items,
        span,
      };
    });

    const uniqueBusesWeek = new Set(
      DAYS.flatMap((day) => (scheduleByDay?.[day]?.schedule || []).map((bus) => String(bus?.bus_id || ''))),
    );
    uniqueBusesWeek.delete('');

    const topSchools = [...schools.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([name, value], _, arr) => ({
        name,
        value,
        percent: arr[0] ? (value / arr[0][1]) * 100 : 0,
      }));

    const topContracts = [...contracts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([name, value], _, arr) => ({
        name,
        value,
        percent: arr[0] ? (value / arr[0][1]) * 100 : 0,
      }));

    const topZones = [...zones.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([name, value], _, arr) => ({
        name,
        value,
        percent: arr[0] ? (value / arr[0][1]) * 100 : 0,
      }));

    return {
      routesTotal: allRoutes.length,
      schoolsTotal: schools.size,
      contractsTotal: contracts.size,
      zonesTotal: zones.size,
      totalStops,
      totalPeakStudents,
      maxRouteStudents,
      activeDayBuses: scheduleByDay?.[activeDay]?.schedule?.length || 0,
      uniqueBusesWeek: uniqueBusesWeek.size,
      byDayRows,
      topSchools,
      topContracts,
      topZones,
    };
  }, [routes, scheduleByDay, activeDay]);

  return (
    <div className="h-full w-full min-h-0 overflow-auto control-panel rounded-[14px] p-4 md:p-5">
      <div className="flex items-end justify-between mb-4">
        <div>
          <p className="text-[12px] uppercase tracking-[0.14em] text-cyan-300 data-mono">Control Dashboard</p>
          <h2 className="text-[20px] font-semibold text-[#e7f0f8] mt-1">Resumen Operativo del Sistema</h2>
        </div>
        <p className="text-[10px] uppercase tracking-[0.1em] text-slate-500">
          Vista agregada de rutas, colegios y cobertura
        </p>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={Bus} label="Rutas Totales" value={data.routesTotal} />
        <KpiCard icon={Building2} label="Colegios" value={data.schoolsTotal} tone="text-indigo-300" />
        <KpiCard icon={FileText} label="Contratos" value={data.contractsTotal} tone="text-amber-300" />
        <KpiCard icon={Compass} label="Zonas" value={data.zonesTotal} tone="text-emerald-300" />
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3 mb-4">
        <KpiCard
          icon={Users}
          label="Pico Alumnos (Suma)"
          value={data.totalPeakStudents}
          tone="text-cyan-200"
          subtitle={`Maximo en una ruta: ${data.maxRouteStudents}`}
        />
        <KpiCard icon={MapPin} label="Paradas Totales" value={data.totalStops} tone="text-slate-200" />
        <KpiCard icon={BarChart3} label={`Buses ${DAY_LABELS[activeDay] || activeDay}`} value={data.activeDayBuses} tone="text-fuchsia-300" />
        <KpiCard icon={Bus} label="Buses Unicos Semana" value={data.uniqueBusesWeek} tone="text-sky-300" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-3 mb-4">
        <HorizontalBars title="Top Colegios por Rutas" rows={data.topSchools} colorClass="bg-cyan-400" />
        <HorizontalBars title="Top Contratos por Rutas" rows={data.topContracts} colorClass="bg-amber-400" />
        <HorizontalBars title="Top Zonas Operativas" rows={data.topZones} colorClass="bg-emerald-400" />
      </div>

      <div className="control-card rounded-[12px] p-4 border border-[#2f465d]">
        <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500 mb-3">Carga Operativa por Dia</p>
        <div className="overflow-x-auto">
          <table className="w-full text-[11px] min-w-[520px]">
            <thead>
              <tr className="text-slate-500 uppercase tracking-[0.08em]">
                <th className="text-left font-medium pb-2">Dia</th>
                <th className="text-right font-medium pb-2">Buses</th>
                <th className="text-right font-medium pb-2">Rutas</th>
                <th className="text-right font-medium pb-2">Franja Horaria</th>
              </tr>
            </thead>
            <tbody>
              {data.byDayRows.map((row) => (
                <tr key={row.day} className="border-t border-[#24384d]">
                  <td className="py-2.5 text-slate-200">{row.label}</td>
                  <td className="py-2.5 text-right data-mono text-cyan-300">{row.buses}</td>
                  <td className="py-2.5 text-right data-mono text-slate-300">{row.items}</td>
                  <td className="py-2.5 text-right data-mono text-slate-400">{row.span}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
