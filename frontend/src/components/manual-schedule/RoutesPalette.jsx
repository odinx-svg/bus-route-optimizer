import React, { useState, useMemo } from 'react';
import { RouteCard, RouteCardSkeleton } from './RouteCard';
import { Edit3, Copy, Trash2, MoreVertical } from 'lucide-react';

// Helper para convertir tiempo a minutos
function timeToMinutes(timeStr) {
  if (!timeStr) return 0;
  const [hours, minutes] = timeStr.split(':').map(Number);
  return (hours || 0) * 60 + (minutes || 0);
}

/**
 * FilterButton - Botón de filtro con estado activo/inactivo
 */
function FilterButton({ active, onClick, children, count, color = 'indigo' }) {
  const colors = {
    indigo: {
      active: 'bg-gt-info text-white shadow-gt-glow',
      inactive: 'gt-glass text-gt-text-muted hover:bg-white/5',
    },
    amber: {
      active: 'bg-gt-warning text-white shadow-[0_0_12px_rgba(245,158,11,0.4)]',
      inactive: 'gt-glass text-gt-text-muted hover:bg-white/5',
    },
    all: {
      active: 'bg-gt-text-muted text-white shadow-lg',
      inactive: 'gt-glass text-gt-text-muted hover:bg-white/5',
    },
  };

  const theme = colors[color] || colors.indigo;

  return (
    <button
      onClick={onClick}
      className={`
        px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200
        ${active ? theme.active : theme.inactive}
      `}
    >
      <span>{children}</span>
      {count !== undefined && (
        <span className={`
          ml-1.5 px-1.5 py-0.5 rounded-full text-[10px]
          ${active ? 'bg-white/20' : 'bg-gt-card text-gt-text-muted'}
        `}>
          {count}
        </span>
      )}
    </button>
  );
}

/**
 * SearchInput - Campo de búsqueda
 */
function SearchInput({ value, onChange, placeholder = 'Buscar ruta...' }) {
  return (
    <div className="relative">
      <svg 
        className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gt-text-muted"
        fill="none" 
        viewBox="0 0 24 24" 
        stroke="currentColor"
      >
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="
          w-full pl-9 pr-3 py-2 rounded-xl bg-gt-card border border-gt-border
          text-sm text-gt-text placeholder-gt-text-muted
          focus:outline-none focus:border-gt-accent/30
          transition-all duration-200
        "
      />
      {value && (
        <button
          onClick={() => onChange('')}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-gt-text-muted hover:text-gt-text"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      )}
    </div>
  );
}

/**
 * SortSelect - Selector de ordenamiento
 */
function SortSelect({ value, onChange }) {
  const options = [
    { value: 'time', label: 'Por hora' },
    { value: 'code', label: 'Por código' },
    { value: 'duration', label: 'Por duración' },
  ];

  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="
          w-full px-3 py-2 pr-8 rounded-xl bg-gt-card border border-gt-border
          text-xs text-gt-text appearance-none cursor-pointer
          focus:outline-none focus:border-gt-accent/30
        "
      >
        {options.map(opt => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
      <svg 
        className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gt-text-muted pointer-events-none"
        fill="none" 
        viewBox="0 0 24 24" 
        stroke="currentColor"
      >
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
      </svg>
    </div>
  );
}

/**
 * RouteCardWithActions - Tarjeta de ruta con menú de acciones
 */
function RouteCardWithActions({ route, onEdit, onDuplicate, onDelete }) {
  const [showMenu, setShowMenu] = useState(false);

  return (
    <div className="relative group">
      {/* RouteCard normal */}
      <div onClick={() => setShowMenu(!showMenu)}>
        <RouteCard route={route} />
      </div>
      
      {/* Menú de acciones */}
      {showMenu && (
        <>
          <div 
            className="fixed inset-0 z-40"
            onClick={() => setShowMenu(false)}
          />
          <div className="absolute top-0 right-0 z-50 mt-1 mr-1 gt-glass rounded-xl shadow-xl border border-gt-border py-1 min-w-[120px]">
            <button
              onClick={(e) => { e.stopPropagation(); onEdit?.(route); setShowMenu(false); }}
              className="w-full px-3 py-2 text-left text-xs text-gt-text hover:bg-white/5 flex items-center gap-2"
            >
              <Edit3 className="w-3.5 h-3.5" />
              Editar
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onDuplicate?.(route); setShowMenu(false); }}
              className="w-full px-3 py-2 text-left text-xs text-gt-text hover:bg-white/5 flex items-center gap-2"
            >
              <Copy className="w-3.5 h-3.5" />
              Duplicar
            </button>
            <div className="border-t border-gt-border my-1" />
            <button
              onClick={(e) => { e.stopPropagation(); onDelete?.(route); setShowMenu(false); }}
              className="w-full px-3 py-2 text-left text-xs text-gt-danger hover:bg-gt-danger/10 flex items-center gap-2"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Eliminar
            </button>
          </div>
        </>
      )}
      
      {/* Indicador de menú (visible en hover) */}
      <div 
        className="absolute top-1 right-1 z-10 opacity-0 group-hover:opacity-100 transition-opacity"
        onClick={(e) => { e.stopPropagation(); setShowMenu(true); }}
      >
        <div className="p-1 bg-black/30 hover:bg-black/50 rounded cursor-pointer">
          <MoreVertical className="w-3 h-3 text-white" />
        </div>
      </div>
    </div>
  );
}

/**
 * EmptyState - Estado vacío cuando no hay rutas
 */
function EmptyState({ filter }) {
  const messages = {
    all: 'No hay rutas disponibles',
    entry: 'No hay rutas de entrada',
    exit: 'No hay rutas de salida',
    search: 'No se encontraron rutas',
  };

  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <div className="w-12 h-12 rounded-full gt-glass flex items-center justify-center mb-3">
        <svg className="w-6 h-6 text-gt-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0121 18.382V7.618a1 1 0 01-.806-.984A1 1 0 0120 6.618L15 7m0 13V7" />
        </svg>
      </div>
      <p className="text-sm text-gt-text-muted">{messages[filter] || messages.all}</p>
    </div>
  );
}

/**
 * RoutesPalette - Panel lateral de rutas disponibles
 */
export function RoutesPalette({ 
  routes = [], 
  isLoading = false,
  title = 'Rutas Disponibles',
  onRouteClick,
  onRouteEdit,
  onRouteDuplicate,
  onRouteDelete,
}) {
  const [filter, setFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('time');

  // Contadores por tipo (con protección)
  const counts = useMemo(() => ({
    all: routes?.length || 0,
    entry: routes?.filter(r => r?.type === 'entry').length || 0,
    exit: routes?.filter(r => r?.type === 'exit').length || 0,
  }), [routes]);

  // Filtrar y ordenar rutas
  const filteredRoutes = useMemo(() => {
    if (!routes || routes.length === 0) return [];
    
    let result = [...routes];

    // Filtrar por tipo
    if (filter !== 'all') {
      result = result.filter(r => r?.type === filter);
    }

    // Filtrar por búsqueda (con protección contra undefined)
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(r => 
        (r.code || '').toLowerCase().includes(query) ||
        (r.origin || '').toLowerCase().includes(query) ||
        (r.destination || '').toLowerCase().includes(query)
      );
    }

    // Ordenar (con protección contra undefined)
    result.sort((a, b) => {
      // Verificar que los datos existan
      if (!a || !b) return 0;
      
      switch (sortBy) {
        case 'time':
          return (a.startTime || '').localeCompare(b.startTime || '');
        case 'code':
          return (a.code || '').localeCompare(b.code || '');
        case 'duration':
          const durA = timeToMinutes(a.endTime) - timeToMinutes(a.startTime);
          const durB = timeToMinutes(b.endTime) - timeToMinutes(b.startTime);
          return durB - durA;
        default:
          return 0;
      }
    });

    return result;
  }, [routes, filter, searchQuery, sortBy]);

  return (
    <div className="w-full gt-sidebar rounded-2xl flex flex-col h-full overflow-hidden">
      {/* Header - solo si hay título */}
      {title && (
        <div className="p-4 gt-border-b">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-gt-text font-bold flex items-center gap-2">
              <svg className="w-4 h-4 text-gt-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
              </svg>
              {title}
            </h3>
            <span className="text-xs text-gt-text-muted bg-gt-card px-2 py-0.5 rounded-full">
              {routes.length}
            </span>
          </div>
        </div>
      )}

      {/* Búsqueda - siempre visible */}
      <div className="px-4 py-3 gt-border-b">
        <SearchInput 
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Buscar código, origen, destino..."
        />
      </div>

      {/* Filtros */}
      <div className="px-4 py-3 gt-border-b">
        <div className="flex gap-2 mb-3">
          <FilterButton 
            active={filter === 'all'} 
            onClick={() => setFilter('all')}
            count={counts.all}
            color="all"
          >
            Todas
          </FilterButton>
          <FilterButton 
            active={filter === 'entry'} 
            onClick={() => setFilter('entry')}
            count={counts.entry}
            color="indigo"
          >
            Entradas
          </FilterButton>
          <FilterButton 
            active={filter === 'exit'} 
            onClick={() => setFilter('exit')}
            count={counts.exit}
            color="amber"
          >
            Salidas
          </FilterButton>
        </div>

        {/* Ordenamiento */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Ordenar:</span>
          <SortSelect value={sortBy} onChange={setSortBy} />
        </div>
      </div>

      {/* Grid de rutas */}
      <div className="flex-1 overflow-y-auto p-4">
        {isLoading ? (
          <div className="grid grid-cols-2 gap-2">
            {[...Array(6)].map((_, i) => (
              <RouteCardSkeleton key={i} />
            ))}
          </div>
        ) : filteredRoutes.length === 0 ? (
          <EmptyState filter={searchQuery ? 'search' : filter} />
        ) : (
          <div className="grid grid-cols-2 gap-2">
            {filteredRoutes.map((route, index) => (
              <RouteCardWithActions
                key={route.id ? `${route.id}-${index}` : `route-${index}`}
                route={route}
                onEdit={onRouteEdit || onRouteClick}
                onDuplicate={onRouteDuplicate}
                onDelete={onRouteDelete}
              />
            ))}
          </div>
        )}
      </div>

      {/* Footer con info */}
      <div className="px-4 py-2 gt-border-b gt-stat-card">
        <p className="text-[10px] text-gt-text-muted text-center">
          Arrastra las rutas al workspace para asignarlas
        </p>
      </div>
    </div>
  );
}

/**
 * RoutesPaletteCompact - Versión compacta para layouts reducidos
 */
export function RoutesPaletteCompact({ routes = [], onRouteSelect }) {
  const [filter, setFilter] = useState('all');
  
  const filteredRoutes = routes.filter(r => filter === 'all' || r.type === filter);

  return (
    <div className="w-48 bg-gray-800 rounded-lg border border-gray-700/50 p-3">
      <h4 className="text-xs font-semibold text-gray-300 mb-2">Rutas</h4>
      
      <div className="flex gap-1 mb-2">
        {['all', 'entry', 'exit'].map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`
              px-2 py-0.5 rounded text-[10px] font-medium
              ${filter === f 
                ? 'bg-indigo-500 text-white' 
                : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
              }
            `}
          >
            {f === 'all' ? 'All' : f === 'entry' ? 'In' : 'Out'}
          </button>
        ))}
      </div>

      <div className="space-y-1 max-h-48 overflow-y-auto">
        {filteredRoutes.map((route, index) => (
          <button
            key={route.id ? `${route.id}-${index}` : `route-${index}`}
            onClick={() => onRouteSelect?.(route)}
            className={`
              w-full px-2 py-1.5 rounded text-left text-xs
              ${route.type === 'entry' 
                ? 'bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-200' 
                : 'bg-amber-500/20 hover:bg-amber-500/30 text-amber-200'
              }
              transition-colors duration-150
            `}
          >
            <div className="font-medium truncate">{route.code}</div>
            <div className="text-[10px] opacity-70">{route.startTime} - {route.endTime}</div>
          </button>
        ))}
      </div>
    </div>
  );
}

export default RoutesPalette;
