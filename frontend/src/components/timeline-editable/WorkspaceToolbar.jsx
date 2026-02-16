/**
 * WorkspaceToolbar - Barra de herramientas superior profesional
 * 
 * Inspirado en: Figma, N8N, Linear
 * Características:
 * - Stats en tiempo real
 * - Controles de zoom intuitivos
 * - Modos de vista
 * - Botones de acción principales
 */

import { 
  ZoomIn, 
  ZoomOut, 
  LayoutGrid, 
  List, 
  Save, 
  Plus, 
  Search,
  RotateCcw,
  Maximize2,
  CheckCircle2,
  AlertTriangle,
  Bus
} from 'lucide-react';
import { useState } from 'react';

export function WorkspaceToolbar({ 
  buses, 
  unassignedRoutes, 
  zoom, 
  onZoomChange,
  viewMode,
  onViewModeChange,
  onAddBus,
  onSave,
  timeRange
}) {
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  
  const totalRoutes = buses.reduce((sum, b) => sum + (b.routes?.length || 0), 0);
  const assignedRoutes = totalRoutes;
  const coveragePercentage = totalRoutes > 0 
    ? Math.round((assignedRoutes / (assignedRoutes + unassignedRoutes.length)) * 100) 
    : 100;

  // Determinar estado del horario
  const hasUnassigned = unassignedRoutes.length > 0;
  const hasConflicts = buses.some(b => b.routes.some(r => r.hasConflict));
  
  const statusConfig = hasConflicts 
    ? { icon: AlertTriangle, color: 'text-red-400', bg: 'bg-red-500/10', label: 'Con conflictos' }
    : hasUnassigned 
      ? { icon: AlertTriangle, color: 'text-amber-400', bg: 'bg-amber-500/10', label: 'Incompleto' }
      : { icon: CheckCircle2, color: 'text-green-400', bg: 'bg-green-500/10', label: 'Completo' };

  const StatusIcon = statusConfig.icon;

  const handleZoomIn = () => {
    onZoomChange(Math.min(2, zoom + 0.25));
  };

  const handleZoomOut = () => {
    onZoomChange(Math.max(0.5, zoom - 0.25));
  };

  const handleResetZoom = () => {
    onZoomChange(1);
  };

  return (
    <div className="h-16 bg-[#13131a] border-b border-gray-800 flex items-center justify-between px-4 flex-shrink-0">
      {/* Sección izquierda: Título y stats */}
      <div className="flex items-center gap-6">
        {/* Título */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-indigo-500/10 rounded-lg flex items-center justify-center">
            <Bus className="w-5 h-5 text-indigo-400" />
          </div>
          <div>
            <h2 className="text-white font-semibold text-sm">Editor de Horarios</h2>
            <p className="text-gray-500 text-xs">Arrastra rutas para organizar</p>
          </div>
        </div>

        {/* Divider */}
        <div className="w-px h-8 bg-gray-800" />

        {/* Stats */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-gray-500 text-xs">Buses</span>
            <span className="text-white text-sm font-medium">{buses.length}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-gray-500 text-xs">Rutas</span>
            <span className="text-white text-sm font-medium">{totalRoutes + unassignedRoutes.length}</span>
          </div>
          {unassignedRoutes.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-gray-500 text-xs">Sin asignar</span>
              <span className="text-amber-400 text-sm font-medium">{unassignedRoutes.length}</span>
            </div>
          )}
        </div>

        {/* Divider */}
        <div className="w-px h-8 bg-gray-800" />

        {/* Status badge */}
        <div className={`
          flex items-center gap-2 px-3 py-1.5 rounded-lg
          ${statusConfig.bg}
        `}>
          <StatusIcon className={`w-4 h-4 ${statusConfig.color}`} />
          <span className={`text-xs font-medium ${statusConfig.color}`}>
            {statusConfig.label}
          </span>
        </div>
      </div>

      {/* Sección central: Controles de zoom y vista */}
      <div className="flex items-center gap-2">
        {/* Zoom controls */}
        <div className="flex items-center gap-1 bg-[#0a0a0f] rounded-lg p-1 border border-gray-800">
          <button
            onClick={handleZoomOut}
            disabled={zoom <= 0.5}
            className="p-2 hover:bg-gray-800 rounded-md text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Alejar"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <span className="text-gray-400 text-xs w-14 text-center font-mono">
            {Math.round(zoom * 100)}%
          </span>
          <button
            onClick={handleZoomIn}
            disabled={zoom >= 2}
            className="p-2 hover:bg-gray-800 rounded-md text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Acercar"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <div className="w-px h-4 bg-gray-800 mx-1" />
          <button
            onClick={handleResetZoom}
            className="p-2 hover:bg-gray-800 rounded-md text-gray-400 hover:text-white transition-colors"
            title="Reset zoom"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Divider */}
        <div className="w-px h-8 bg-gray-800 mx-1" />

        {/* View mode toggle */}
        <div className="flex items-center gap-1 bg-[#0a0a0f] rounded-lg p-1 border border-gray-800">
          <button
            onClick={() => onViewModeChange('timeline')}
            className={`
              p-2 rounded-md transition-colors flex items-center gap-1.5
              ${viewMode === 'timeline' 
                ? 'bg-gray-700 text-white' 
                : 'text-gray-400 hover:text-white hover:bg-gray-800'}
            `}
            title="Vista timeline"
          >
            <LayoutGrid className="w-4 h-4" />
            <span className="text-xs">Timeline</span>
          </button>
          <button
            onClick={() => onViewModeChange('compact')}
            className={`
              p-2 rounded-md transition-colors flex items-center gap-1.5
              ${viewMode === 'compact' 
                ? 'bg-gray-700 text-white' 
                : 'text-gray-400 hover:text-white hover:bg-gray-800'}
            `}
            title="Vista compacta"
          >
            <List className="w-4 h-4" />
            <span className="text-xs">Compacto</span>
          </button>
        </div>
      </div>

      {/* Sección derecha: Acciones */}
      <div className="flex items-center gap-2">
        {/* Rango horario */}
        <div className="flex items-center gap-2 px-3 py-1.5 bg-[#0a0a0f] rounded-lg border border-gray-800 mr-2">
          <span className="text-gray-500 text-xs">Horario</span>
          <span className="text-gray-300 text-xs font-mono">
            {String(timeRange?.start || 6).padStart(2, '0')}:00 - {String(timeRange?.end || 22).padStart(2, '0')}:00
          </span>
        </div>

        {/* Botón agregar bus */}
        <button 
          onClick={onAddBus}
          className="
            flex items-center gap-1.5 px-3 py-2 
            bg-indigo-600 hover:bg-indigo-500 
            text-white rounded-lg text-sm font-medium
            transition-colors shadow-lg shadow-indigo-500/20
          "
        >
          <Plus className="w-4 h-4" />
          <span>Bus</span>
        </button>

        {/* Botón guardar */}
        <button 
          onClick={onSave}
          className="
            flex items-center gap-1.5 px-4 py-2 
            bg-green-600 hover:bg-green-500 
            text-white rounded-lg text-sm font-medium
            transition-colors shadow-lg shadow-green-500/20
          "
        >
          <Save className="w-4 h-4" />
          <span>Guardar</span>
        </button>
      </div>
    </div>
  );
}

export default WorkspaceToolbar;
