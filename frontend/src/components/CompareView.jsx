import { useMemo } from 'react';
import { TrendingDown, TrendingUp, Minus } from 'lucide-react';

export function CompareView({ before, after }) {
  const comparison = useMemo(() => {
    return {
      buses: {
        before: before?.length || 0,
        after: after?.length || 0,
        change: ((after?.length || 0) - (before?.length || 0))
      },
      totalRoutes: {
        before: countRoutes(before),
        after: countRoutes(after),
        change: countRoutes(after) - countRoutes(before)
      },
      avgRoutesPerBus: {
        before: avgRoutes(before),
        after: avgRoutes(after),
        change: avgRoutes(after) - avgRoutes(before)
      },
      deadhead: {
        before: calculateDeadhead(before),
        after: calculateDeadhead(after),
        change: calculateDeadhead(after) - calculateDeadhead(before)
      }
    };
  }, [before, after]);

  return (
    <div className="bg-white rounded-lg shadow border p-6">
      <h2 className="text-xl font-bold mb-6">Comparación de Optimización</h2>
      
      <div className="grid grid-cols-4 gap-4 mb-6">
        <MetricCard
          title="Buses"
          metric={comparison.buses}
          lowerIsBetter={true}
        />
        <MetricCard
          title="Rutas Totales"
          metric={comparison.totalRoutes}
          lowerIsBetter={false}
        />
        <MetricCard
          title="Rutas/Bus (avg)"
          metric={comparison.avgRoutesPerBus}
          lowerIsBetter={false}
        />
        <MetricCard
          title="Km en Vacío"
          metric={comparison.deadhead}
          lowerIsBetter={true}
          unit="km"
        />
      </div>

      <SavingsSummary comparison={comparison} />
    </div>
  );
}

function MetricCard({ title, metric, lowerIsBetter, unit = '' }) {
  const isPositive = lowerIsBetter ? metric.change < 0 : metric.change > 0;
  const Icon = isPositive ? TrendingDown : metric.change === 0 ? Minus : TrendingUp;
  const colorClass = isPositive ? 'text-green-600' : metric.change === 0 ? 'text-gray-500' : 'text-red-600';
  const bgClass = isPositive ? 'bg-green-50' : metric.change === 0 ? 'bg-gray-50' : 'bg-red-50';

  const percentChange = metric.before !== 0 
    ? ((metric.change / metric.before) * 100).toFixed(1)
    : 0;

  return (
    <div className={`${bgClass} rounded-lg p-4`}>
      <div className="text-sm text-gray-600 mb-1">{title}</div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold">{metric.after}{unit}</span>
        <span className="text-sm text-gray-400">/ {metric.before}{unit}</span>
      </div>
      <div className={`flex items-center gap-1 mt-2 ${colorClass}`}>
        <Icon className="w-4 h-4" />
        <span className="font-medium">
          {metric.change > 0 ? '+' : ''}{metric.change}{unit}
        </span>
        <span className="text-sm">
          ({percentChange}%)
        </span>
      </div>
    </div>
  );
}

function SavingsSummary({ comparison }) {
  const busSavings = comparison.buses.before - comparison.buses.after;
  
  if (busSavings <= 0) return null;

  // Estimación conservadora: €300/día por bus ahorrado
  const dailySavings = busSavings * 300;
  const monthlySavings = dailySavings * 22;
  const yearlySavings = monthlySavings * 12;

  return (
    <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-lg">
      <h3 className="font-semibold text-green-800 mb-2">
        💰 Estimación de Ahorros
      </h3>
      <p className="text-sm text-green-700 mb-3">
        Reduciendo {busSavings} bus(es) de la flota:
      </p>
      <div className="grid grid-cols-3 gap-4 text-center">
        <div>
          <div className="text-2xl font-bold text-green-600">
            €{dailySavings.toLocaleString()}
          </div>
          <div className="text-xs text-green-700">por día</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-green-600">
            €{monthlySavings.toLocaleString()}
          </div>
          <div className="text-xs text-green-700">por mes</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-green-600">
            €{yearlySavings.toLocaleString()}
          </div>
          <div className="text-xs text-green-700">por año</div>
        </div>
      </div>
    </div>
  );
}

// Helpers
function countRoutes(schedule) {
  return schedule?.reduce((sum, bus) => sum + bus.items.length, 0) || 0;
}

function avgRoutes(schedule) {
  if (!schedule?.length) return 0;
  return (countRoutes(schedule) / schedule.length).toFixed(1);
}

function calculateDeadhead(schedule) {
  // Simplificación - en realidad calcularía con coordenadas
  return schedule?.length * 15 || 0; // Placeholder
}
