import React from 'react';
import { Loader2, Sparkles, MapPin, Bus, Clock, WifiOff, Database } from 'lucide-react';

export function TimelineLoading({ message = 'Cargando timeline...', submessage = 'Organizando rutas', progress = null }) {
  return (
    <div className="flex items-center justify-center h-64 animate-in fade-in duration-300">
      <div className="text-center">
        <div className="relative w-16 h-16 mx-auto mb-4">
          <div className="absolute inset-0 border-4 border-indigo-500/20 rounded-full" />
          <div className="absolute inset-0 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          <Clock className="absolute inset-0 m-auto w-6 h-6 text-indigo-400" />
        </div>
        <p className="text-gray-200 font-medium">{message}</p>
        <p className="text-gray-500 text-sm mt-1">{submessage}</p>
        {progress !== null && (
          <div className="mt-4 w-48 mx-auto">
            <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
              <div className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function SuggestionsLoading({ count = 3, showAiSparkle = true }) {
  return (
    <div className="space-y-3 animate-in fade-in">
      {showAiSparkle && (
        <div className="flex items-center gap-2 text-indigo-400 text-sm mb-3">
          <Sparkles className="w-4 h-4 animate-pulse" />
          <span>La IA está analizando las mejores opciones...</span>
        </div>
      )}
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="h-24 bg-gray-800/50 rounded-lg animate-pulse" style={{ animationDelay: `${i * 150}ms` }}>
          <div className="h-full flex items-center px-4 gap-3">
            <div className="w-10 h-10 rounded-full bg-gray-700/50" />
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-gray-700/50 rounded w-3/4" />
              <div className="h-3 bg-gray-700/50 rounded w-1/2" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function ValidatingIndicator({ message = 'Validando compatibilidad...', details = null }) {
  return (
    <div className="fixed bottom-4 right-4 z-50 animate-in slide-in-from-bottom-2">
      <div className="bg-indigo-900/95 backdrop-blur-sm text-white px-4 py-3 rounded-xl shadow-xl border border-indigo-500/30 flex items-center gap-3">
        <Loader2 className="w-5 h-5 animate-spin" />
        <div>
          <p className="text-sm font-medium">{message}</p>
          {details && <p className="text-indigo-300 text-xs">{details}</p>}
        </div>
      </div>
    </div>
  );
}

export function RoutesLoading({ count = 5 }) {
  return (
    <div className="space-y-2 animate-in fade-in">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 p-3 bg-gray-800/30 rounded-lg animate-pulse" style={{ animationDelay: `${i * 100}ms` }}>
          <div className="w-2 h-12 bg-gray-700 rounded" />
          <div className="flex-1 space-y-2">
            <div className="h-4 bg-gray-700 rounded w-24" />
            <div className="h-3 bg-gray-700 rounded w-16" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function BusesLoading({ count = 3 }) {
  return (
    <div className="space-y-4 animate-in fade-in">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="bg-gray-800/30 rounded-lg p-4 animate-pulse" style={{ animationDelay: `${i * 200}ms` }}>
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-full bg-gray-700" />
            <div className="h-4 bg-gray-700 rounded w-20" />
          </div>
          <div className="h-20 bg-gray-700/50 rounded" />
        </div>
      ))}
    </div>
  );
}

export function MapLoading() {
  return (
    <div className="h-full flex items-center justify-center bg-gray-900/50 rounded-lg animate-in fade-in">
      <div className="text-center">
        <MapPin className="w-10 h-10 text-emerald-400 mx-auto mb-3 animate-pulse" />
        <p className="text-gray-300 font-medium">Cargando mapa...</p>
      </div>
    </div>
  );
}

export function OfflineIndicator({ onRetry }) {
  return (
    <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 animate-in slide-in-from-top">
      <div className="bg-amber-900/90 text-amber-100 px-4 py-2 rounded-full shadow-lg border border-amber-500/30 flex items-center gap-3">
        <WifiOff className="w-4 h-4" />
        <span className="text-sm">Sin conexión - Modo offline</span>
        {onRetry && <button onClick={onRetry} className="ml-2 px-3 py-1 bg-amber-700 rounded-full text-xs">Reintentar</button>}
      </div>
    </div>
  );
}

export function FallbackIndicator({ source = 'caché local' }) {
  return (
    <div className="bg-blue-900/30 border border-blue-500/30 rounded-lg p-3 flex items-center gap-3 text-blue-300 text-sm">
      <Database className="w-4 h-4" />
      <span>Mostrando datos desde {source}</span>
    </div>
  );
}

export function SlowConnectionIndicator() {
  return (
    <div className="flex items-center gap-2 text-amber-400 text-sm animate-pulse">
      <Loader2 className="w-4 h-4 animate-spin" />
      <span>Conexión lenta...</span>
    </div>
  );
}

export function TimelineSkeleton() {
  return (
    <div className="h-96 bg-gray-800/20 rounded-lg overflow-hidden animate-pulse">
      <div className="h-12 bg-gray-800/50 border-b border-gray-700" />
      <div className="p-4 space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-16 bg-gray-800/30 rounded flex items-center px-4 gap-3">
            <div className="w-20 h-8 bg-gray-700 rounded" />
            <div className="flex-1 h-8 bg-gray-700/50 rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function ProgressiveLoading({ steps, currentStep }) {
  return (
    <div className="space-y-3">
      {steps.map((step, index) => {
        const isDone = index < currentStep;
        const isActive = index === currentStep;
        return (
          <div key={step.id} className={`flex items-center gap-3 p-3 rounded-lg transition-all ${
            isDone ? 'bg-green-900/20 text-green-400' : isActive ? 'bg-indigo-900/20 text-indigo-400 border border-indigo-500/30' : 'bg-gray-800/30 text-gray-600'
          }`}>
            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
              isDone ? 'bg-green-500 text-white' : isActive ? 'bg-indigo-500 text-white animate-pulse' : 'bg-gray-700'
            }`}>
              {isDone ? '✓' : isActive ? <Loader2 className="w-3 h-3 animate-spin" /> : index + 1}
            </div>
            <span className="text-sm font-medium">{step.label}</span>
          </div>
        );
      })}
    </div>
  );
}

export default TimelineLoading;
