import { CheckCircle, XCircle, BarChart3, AlertCircle, Lightbulb } from 'lucide-react';

export function MonteCarloResults({ grade, feasibleRate, stats }) {
  const interpretations = {
    'A': {
      title: 'Horario Excelente',
      desc: 'Muy robusto. Resiste bien las variaciones de tráfico y condiciones imprevistas.',
      color: 'text-green-400',
      bgColor: 'bg-green-400/10',
      borderColor: 'border-green-400/30',
      icon: CheckCircle,
      recommendation: 'El horario está listo para implementación. Puedes confiar en que funcionará bien la mayoría de los días.'
    },
    'B': {
      title: 'Horario Bueno',
      desc: 'Generalmente funciona bien, pero algunos días puede tener retrasos menores.',
      color: 'text-green-300',
      bgColor: 'bg-green-300/10',
      borderColor: 'border-green-300/30',
      icon: CheckCircle,
      recommendation: 'Considerar añadir pequeños buffers (5-10 min) en las rutas más críticas para mejorar la confiabilidad.'
    },
    'C': {
      title: 'Horario Aceptable',
      desc: 'Funciona la mayoría de días, pero hay margen de mejora significativo.',
      color: 'text-yellow-400',
      bgColor: 'bg-yellow-400/10',
      borderColor: 'border-yellow-400/30',
      icon: AlertCircle,
      recommendation: 'Revisar tiempos de traslado y ajustar buffers. Algunas rutas pueden necesitar tiempos más realistas.'
    },
    'D': {
      title: 'Horario Débil',
      desc: 'Frecuentemente tiene problemas con variaciones normales de tráfico.',
      color: 'text-orange-400',
      bgColor: 'bg-orange-400/10',
      borderColor: 'border-orange-400/30',
      icon: AlertCircle,
      recommendation: 'Necesita optimización urgente. Aumentar tiempos entre rutas consecutivas y revisar asignaciones de buses.'
    },
    'F': {
      title: 'Horario No Viable',
      desc: 'Muy frágil. Falla ante la mayoría de imprevistos y variaciones de tráfico.',
      color: 'text-red-400',
      bgColor: 'bg-red-400/10',
      borderColor: 'border-red-400/30',
      icon: XCircle,
      recommendation: 'URGENTE: Reoptimizar con mayores márgenes de tiempo. El horario actual no es práctico para operación real.'
    }
  };
  
  const interp = interpretations[grade] || interpretations['F'];
  const IconComponent = interp.icon;
  
  // Calcular porcentaje formateado
  const successRate = feasibleRate !== undefined 
    ? (feasibleRate * 100).toFixed(1) 
    : stats?.feasibleRate !== undefined 
      ? (stats.feasibleRate * 100).toFixed(1)
      : '0.0';
  
  return (
    <div className="bg-gray-800 p-5 rounded-lg border border-gray-700">
      {/* Header con grado y título */}
      <div className="flex items-center gap-4 mb-4">
        <div className={`p-3 rounded-lg ${interp.bgColor} border ${interp.borderColor}`}>
          <IconComponent className={`w-8 h-8 ${interp.color}`} />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h4 className={`text-xl font-bold ${interp.color}`}>
              {interp.title}
            </h4>
            <span className={`px-3 py-1 rounded-full text-sm font-bold ${interp.bgColor} ${interp.color} border ${interp.borderColor}`}>
              Grado {grade}
            </span>
          </div>
          <p className="text-gray-400 text-sm mt-1">{interp.desc}</p>
        </div>
      </div>
      
      {/* Barra de progreso visual */}
      <div className="mb-4">
        <div className="flex justify-between text-sm mb-2">
          <span className="text-gray-400">Tasa de éxito</span>
          <span className={`font-bold ${interp.color}`}>{successRate}%</span>
        </div>
        <div className="h-3 bg-gray-700 rounded-full overflow-hidden">
          <div 
            className={`h-full rounded-full transition-all duration-500 ${
              grade === 'A' ? 'bg-green-400' :
              grade === 'B' ? 'bg-green-300' :
              grade === 'C' ? 'bg-yellow-400' :
              grade === 'D' ? 'bg-orange-400' : 'bg-red-400'
            }`}
            style={{ width: `${Math.min(parseFloat(successRate), 100)}%` }}
          />
        </div>
      </div>
      
      {/* Recomendación */}
      <div className="p-4 bg-gray-900 rounded-lg border border-gray-700 mb-4">
        <div className="flex items-start gap-3">
          <Lightbulb className="w-5 h-5 text-yellow-400 mt-0.5 flex-shrink-0" />
          <div>
            <span className="text-sm text-gray-400 font-medium">Recomendación:</span>
            <p className="text-white mt-1 leading-relaxed">{interp.recommendation}</p>
          </div>
        </div>
      </div>
      
      {/* Estadísticas */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-gray-900 p-3 rounded-lg text-center border border-gray-700">
          <div className="flex items-center justify-center gap-2 mb-1">
            <BarChart3 className="w-4 h-4 text-blue-400" />
            <span className="text-2xl font-bold text-white">
              {stats?.total || stats?.totalScenarios || 0}
            </span>
          </div>
          <div className="text-xs text-gray-400">Simulaciones</div>
        </div>
        <div className="bg-gray-900 p-3 rounded-lg text-center border border-gray-700">
          <div className="flex items-center justify-center gap-2 mb-1">
            <CheckCircle className="w-4 h-4 text-green-400" />
            <span className="text-2xl font-bold text-green-400">
              {stats?.feasible || stats?.feasibleCount || 0}
            </span>
          </div>
          <div className="text-xs text-gray-400">Exitosas</div>
        </div>
        <div className="bg-gray-900 p-3 rounded-lg text-center border border-gray-700">
          <div className="flex items-center justify-center gap-2 mb-1">
            <XCircle className="w-4 h-4 text-red-400" />
            <span className="text-2xl font-bold text-red-400">
              {stats?.infeasible || stats?.infeasibleCount || 0}
            </span>
          </div>
          <div className="text-xs text-gray-400">Con conflictos</div>
        </div>
      </div>
    </div>
  );
}
