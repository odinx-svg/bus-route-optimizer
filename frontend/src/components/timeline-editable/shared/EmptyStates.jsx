import React from 'react';
import { ClipboardList, PackageOpen, Lock, Search, Inbox, FileSpreadsheet, Bus, MapPin, AlertCircle, RefreshCw, Plus, Upload, Sparkles, Clock } from 'lucide-react';

function ActionButton({ onClick, icon: Icon, children, variant = 'primary' }) {
  const variants = {
    primary: 'bg-indigo-600 hover:bg-indigo-500 text-white',
    secondary: 'bg-gray-700 hover:bg-gray-600 text-white',
    ghost: 'bg-transparent hover:bg-gray-800 text-gray-400 hover:text-white'
  };
  return (
    <button onClick={onClick} className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${variants[variant]}`}>
      {Icon && <Icon className="w-4 h-4" />}{children}
    </button>
  );
}

export function NoRoutesEmptyState({ onUpload, onDemo }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 text-center px-4 animate-in fade-in zoom-in-95 duration-300">
      <div className="relative mb-4">
        <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-gray-800 to-gray-900 flex items-center justify-center border border-gray-700">
          <ClipboardList className="w-10 h-10 text-gray-500" />
        </div>
        <div className="absolute -bottom-1 -right-1 w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center animate-bounce">
          <Plus className="w-5 h-5 text-white" />
        </div>
      </div>
      <h3 className="text-xl font-semibold text-gray-300 mb-2">No hay rutas cargadas</h3>
      <p className="text-gray-500 text-sm max-w-sm mb-6">Sube archivos Excel con los datos de rutas o utiliza datos de demostración</p>
      <div className="flex flex-wrap gap-3 justify-center">
        {onUpload && <ActionButton onClick={onUpload} icon={Upload} variant="primary">Subir archivo Excel</ActionButton>}
        {onDemo && <ActionButton onClick={onDemo} icon={Sparkles} variant="secondary">Usar datos demo</ActionButton>}
      </div>
      <p className="text-gray-600 text-xs mt-6">💡 Soporta archivos .xlsx con columnas: ruta, bus, inicio, fin</p>
    </div>
  );
}

export function NoUnassignedRoutes({ onCreateMapPin, compact = false }) {
  if (compact) {
    return (
      <div className="text-center py-6 text-gray-500 animate-in fade-in">
        <PackageOpen className="w-8 h-8 mx-auto mb-2 text-gray-600" />
        <p className="text-sm">No hay rutas libres</p>
      </div>
    );
  }
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center px-4 animate-in fade-in">
      <div className="w-16 h-16 rounded-full bg-gray-800 flex items-center justify-center mb-4">
        <PackageOpen className="w-8 h-8 text-gray-500" />
      </div>
      <h3 className="text-lg font-medium text-gray-300 mb-1">No hay rutas libres</h3>
      <p className="text-gray-500 text-sm max-w-xs mb-4">Todas las rutas están asignadas. Arrastra rutas aquí para liberarlas.</p>
      <div className="flex items-center gap-2 text-gray-600 text-xs">
        <span className="px-2 py-1 bg-gray-800 rounded">Arrastra</span>
        <span>una ruta desde un bus para liberarla</span>
      </div>
    </div>
  );
}

export function AllRoutesLocked({ onUnlockAll, lockedCount }) {
  return (
    <div className="bg-amber-900/20 border border-amber-500/30 rounded-xl p-6 text-center animate-in fade-in">
      <div className="flex items-center justify-center mb-3">
        <div className="w-12 h-12 rounded-full bg-amber-500/20 flex items-center justify-center">
          <Lock className="w-6 h-6 text-amber-400" />
        </div>
      </div>
      <h3 className="text-amber-400 font-semibold text-lg mb-1">⚠️ Todas las rutas están bloqueadas</h3>
      <p className="text-amber-400/70 text-sm mb-4">Desbloquea alguna ruta para poder editar el horario</p>
      {lockedCount && <p className="text-amber-400/50 text-xs mb-4">{lockedCount} rutas bloqueadas</p>}
      {onUnlockAll && <ActionButton onClick={onUnlockAll} icon={Lock} variant="secondary">Desbloquear todas</ActionButton>}
    </div>
  );
}

export function NoSearchResults({ query, onClear, suggestions = [] }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center px-4 animate-in fade-in">
      <div className="w-16 h-16 rounded-full bg-gray-800 flex items-center justify-center mb-4">
        <Search className="w-8 h-8 text-gray-500" />
      </div>
      <h3 className="text-lg font-medium text-gray-300 mb-1">No se encontraron resultados</h3>
      <p className="text-gray-500 text-sm mb-4">No hay rutas que coincidan con "<span className="text-gray-300">{query}</span>"</p>
      {suggestions.length > 0 && (
        <div className="mb-4">
          <p className="text-gray-600 text-xs mb-2">¿Quizás buscabas?</p>
          <div className="flex flex-wrap gap-2 justify-center">
            {suggestions.map((s, i) => (
              <button key={i} onClick={() => onClear?.(s)} className="px-3 py-1 bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs rounded-full">{s}</button>
            ))}
          </div>
        </div>
      )}
      <ActionButton onClick={() => onClear?.('')} icon={RefreshCw} variant="ghost">Limpiar búsqueda</ActionButton>
    </div>
  );
}

export function NoBusesEmptyState({ onAddBus, onImport }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 text-center px-4 animate-in fade-in">
      <div className="relative mb-4">
        <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-gray-800 to-gray-900 flex items-center justify-center border border-gray-700">
          <Bus className="w-10 h-10 text-gray-500" />
        </div>
        <div className="absolute -top-1 -right-1 w-6 h-6 rounded-full bg-red-500 flex items-center justify-center">
          <AlertCircle className="w-4 h-4 text-white" />
        </div>
      </div>
      <h3 className="text-xl font-semibold text-gray-300 mb-2">No hay buses configurados</h3>
      <p className="text-gray-500 text-sm max-w-sm mb-6">Necesitas al menos un bus para poder asignar rutas</p>
      <div className="flex flex-wrap gap-3 justify-center">
        {onAddBus && <ActionButton onClick={onAddBus} icon={Plus} variant="primary">Agregar bus</ActionButton>}
        {onImport && <ActionButton onClick={onImport} icon={FileSpreadsheet} variant="secondary">Importar desde Excel</ActionButton>}
      </div>
    </div>
  );
}

export function EmptyTimeline({ busesCount, onAssignRoutes, onAutoAssign }) {
  return (
    <div className="flex flex-col items-center justify-center h-80 text-center px-4 animate-in fade-in">
      <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-indigo-900/30 to-purple-900/30 flex items-center justify-center border border-indigo-500/20 mb-4">
        <Clock className="w-12 h-12 text-indigo-400/50" />
      </div>
      <h3 className="text-xl font-semibold text-gray-300 mb-2">Timeline vacío</h3>
      <p className="text-gray-500 text-sm max-w-sm mb-2">
        {busesCount > 0 ? `Tienes ${busesCount} buses pero ninguna ruta asignada` : 'No hay rutas asignadas a ningún bus'}
      </p>
      <div className="flex flex-wrap gap-3 justify-center mt-4">
        {onAssignRoutes && <ActionButton onClick={onAssignMapPins} icon={MapPin} variant="primary">Asignar rutas manualmente</ActionButton>}
        {onAutoAssign && <ActionButton onClick={onAutoAssign} icon={Sparkles} variant="secondary">Asignación automática</ActionButton>}
      </div>
    </div>
  );
}

export function NoHistoryEmptyState() {
  return (
    <div className="text-center py-8 text-gray-500">
      <div className="w-12 h-12 rounded-full bg-gray-800 flex items-center justify-center mx-auto mb-3">
        <Inbox className="w-6 h-6 text-gray-600" />
      </div>
      <p className="text-sm">Sin historial de cambios</p>
      <p className="text-xs text-gray-600 mt-1">Los cambios que realices aparecerán aquí</p>
    </div>
  );
}

export function NoSuggestionsEmptyState({ onRefresh, hasEnoughData }) {
  return (
    <div className="text-center py-8 px-4">
      <div className="w-12 h-12 rounded-full bg-gray-800 flex items-center justify-center mx-auto mb-3">
        <Sparkles className="w-6 h-6 text-gray-600" />
      </div>
      <p className="text-sm text-gray-500 mb-1">{hasEnoughData ? 'No hay sugerencias disponibles' : 'Se necesitan más datos para generar sugerencias'}</p>
      {hasEnoughData && onRefresh && (
        <button onClick={onRefresh} className="text-indigo-400 text-xs hover:text-indigo-300 mt-2 inline-flex items-center gap-1">
          <RefreshCw className="w-3 h-3" /> Generar nuevas sugerencias
        </button>
      )}
    </div>
  );
}

export function LoadErrorState({ error, onRetry, onFallback }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 text-center px-4 animate-in fade-in">
      <div className="w-16 h-16 rounded-full bg-red-900/30 flex items-center justify-center mb-4">
        <AlertCircle className="w-8 h-8 text-red-400" />
      </div>
      <h3 className="text-lg font-semibold text-gray-300 mb-2">Error al cargar datos</h3>
      <p className="text-red-400/70 text-sm max-w-sm mb-4">{error?.message || 'No se pudieron cargar los datos'}</p>
      <div className="flex flex-wrap gap-3 justify-center">
        {onRetry && <ActionButton onClick={onRetry} icon={RefreshCw} variant="primary">Reintentar</ActionButton>}
        {onFallback && <ActionButton onClick={onFallback} icon={FileSpreadsheet} variant="secondary">Usar datos locales</ActionButton>}
      </div>
    </div>
  );
}

export function NoFilterResults({ activeFilters, onClearFilters, resultCount = 0, totalCount = 0 }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center px-4">
      <div className="w-16 h-16 rounded-full bg-gray-800 flex items-center justify-center mb-4">
        <div className="relative">
          <Search className="w-8 h-8 text-gray-500" />
          <div className="absolute -top-1 -right-1 w-4 h-4 bg-gray-700 rounded-full flex items-center justify-center text-xs">{activeFilters.length}</div>
        </div>
      </div>
      <h3 className="text-lg font-medium text-gray-300 mb-1">Filtros activos sin coincidencias</h3>
      {resultCount > 0 && totalCount > 0 && <p className="text-gray-500 text-sm mb-3">Mostrando {resultCount} de {totalCount} rutas</p>}
      <div className="flex flex-wrap gap-2 justify-center mb-4 max-w-xs">
        {activeFilters.map((filter, i) => (
          <span key={i} className="px-2 py-1 bg-indigo-900/30 text-indigo-300 text-xs rounded-full border border-indigo-500/30">{filter.label}: {filter.value}</span>
        ))}
      </div>
      <ActionButton onClick={onClearFilters} icon={RefreshCw} variant="ghost">Limpiar filtros</ActionButton>
    </div>
  );
}

export function EmptyMapState({ onShowAllRoutes }) {
  return (
    <div className="absolute inset-0 flex items-center justify-center bg-gray-900/80 z-10">
      <div className="text-center">
        <div className="w-16 h-16 rounded-full bg-gray-800 flex items-center justify-center mx-auto mb-4">
          <MapPin className="w-8 h-8 text-gray-500" />
        </div>
        <h3 className="text-gray-300 font-medium mb-2">No hay rutas para mostrar</h3>
        <p className="text-gray-500 text-sm mb-4">Selecciona rutas para verlas en el mapa</p>
        {onShowAllRoutes && <ActionButton onClick={onShowAllMapPins} icon={MapPin} variant="primary">Ver todas las rutas</ActionButton>}
      </div>
    </div>
  );
}

export default {
  NoRoutesEmptyState, NoUnassignedRoutes, AllRoutesLocked, NoSearchResults,
  NoBusesEmptyState, EmptyTimeline, NoHistoryEmptyState, NoSuggestionsEmptyState,
  LoadErrorState, NoFilterResults, EmptyMapState
};
