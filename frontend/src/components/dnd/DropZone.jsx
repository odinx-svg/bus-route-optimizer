/**
 * DropZone - Componente genérico de zona de drop
 * 
 * Características:
 * - Indicadores visuales de estado (over, valid, invalid)
 * - Soporte para tipos de datos específicos
 * - Animaciones de transición
 * - Mensajes personalizables
 */
import React from 'react';
import { useDroppable } from '@dnd-kit/core';
import { 
  Plus, 
  CheckCircle2, 
  AlertCircle, 
  XCircle,
  Upload
} from 'lucide-react';

const VARIANTS = {
  default: {
    base: 'border-white/[0.06] bg-zinc-900/20',
    over: 'border-indigo-500/40 bg-indigo-500/[0.05]',
    valid: 'border-emerald-500/40 bg-emerald-500/[0.05]',
    invalid: 'border-red-500/40 bg-red-500/[0.05]',
  },
  dashed: {
    base: 'border-dashed border-white/[0.1] bg-transparent',
    over: 'border-dashed border-indigo-500/50 bg-indigo-500/[0.03]',
    valid: 'border-dashed border-emerald-500/50 bg-emerald-500/[0.03]',
    invalid: 'border-dashed border-red-500/50 bg-red-500/[0.03]',
  },
  minimal: {
    base: 'border-transparent bg-transparent',
    over: 'border-indigo-500/30 bg-indigo-500/[0.03]',
    valid: 'border-emerald-500/30 bg-emerald-500/[0.03]',
    invalid: 'border-red-500/30 bg-red-500/[0.03]',
  },
};

export function DropZone({
  id,
  data = {},
  disabled = false,
  children,
  className = '',
  variant = 'default',
  acceptTypes = [], // ['route', 'assigned-route', 'bus']
  validationFn = null, // (dragData) => { isValid, message }
  onDrop,
  onDragOver,
  onDragLeave,
  // Content customization
  emptyIcon = Plus,
  emptyText = 'Arrastra aquí',
  overText = 'Suelta para agregar',
  invalidText = 'No se puede soltar aquí',
  showIndicator = true,
  minHeight = '120px',
}) {
  const { setNodeRef, isOver, active } = useDroppable({
    id,
    data: {
      type: 'dropzone',
      ...data,
    },
    disabled,
  });

  // Validar si el item arrastrado es aceptado
  const dragData = active?.data?.current;
  const dragType = dragData?.type;
  
  const isAcceptedType = acceptTypes.length === 0 || acceptTypes.includes(dragType);
  
  // Validación personalizada
  let validation = { isValid: true, message: '' };
  if (isOver && validationFn && dragData) {
    validation = validationFn(dragData);
  }
  
  const isValid = isAcceptedType && validation.isValid;
  const showValid = isOver && isValid;
  const showInvalid = isOver && !isValid;

  // Seleccionar clases según estado
  const variantStyles = VARIANTS[variant] || VARIANTS.default;
  let stateClass = variantStyles.base;
  if (showValid) stateClass = variantStyles.valid;
  else if (showInvalid) stateClass = variantStyles.invalid;
  else if (isOver) stateClass = variantStyles.over;

  // Icono según estado
  const getIcon = () => {
    if (showValid) return CheckCircle2;
    if (showInvalid) return XCircle;
    if (isOver) return Upload;
    return emptyIcon;
  };

  const Icon = getIcon();
  const iconColor = showValid ? 'text-emerald-400' : showInvalid ? 'text-red-400' : isOver ? 'text-indigo-400' : 'text-zinc-600';

  return (
    <div
      ref={setNodeRef}
      className={`
        relative rounded-[12px] border-2 transition-all duration-200
        ${stateClass}
        ${disabled ? 'opacity-50 pointer-events-none' : ''}
        ${className}
      `}
      style={{ minHeight }}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
    >
      {children ? (
        // Si hay children, renderizarlos
        <div className="relative z-10">
          {children}
        </div>
      ) : (
        // Si no hay children, mostrar indicador
        showIndicator && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-4">
            <Icon className={`w-8 h-8 ${iconColor} transition-colors duration-200`} />
            <span className={`text-[12px] text-center transition-colors duration-200 ${
              showValid ? 'text-emerald-400' : showInvalid ? 'text-red-400' : isOver ? 'text-indigo-400' : 'text-zinc-500'
            }`}>
              {showValid ? (validation.message || overText) : 
               showInvalid ? (validation.message || invalidText) : 
               isOver ? overText : emptyText}
            </span>
          </div>
        )
      )}

      {/* Overlay de estado */}
      {isOver && (
        <div 
          className={`
            absolute inset-0 rounded-[10px] pointer-events-none
            ${showValid ? 'ring-2 ring-emerald-500/30' : ''}
            ${showInvalid ? 'ring-2 ring-red-500/30' : ''}
          `}
        />
      )}
    </div>
  );
}

/**
 * DropZone.Compact - Versión compacta para uso en listas
 */
export function CompactDropZone({
  id,
  data = {},
  disabled = false,
  isValid = true,
  label = 'Soltar aquí',
  className = '',
}) {
  const { setNodeRef, isOver } = useDroppable({
    id,
    data: { type: 'compact-dropzone', ...data },
    disabled,
  });

  return (
    <div
      ref={setNodeRef}
      className={`
        flex items-center justify-center gap-2 py-2 px-4 rounded-lg
        border border-dashed transition-all duration-150
        ${isOver 
          ? isValid 
            ? 'border-emerald-500/50 bg-emerald-500/5' 
            : 'border-red-500/50 bg-red-500/5'
          : 'border-white/[0.06] bg-transparent hover:border-white/[0.1]'
        }
        ${className}
      `}
    >
      {isOver ? (
        isValid ? (
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
        ) : (
          <AlertCircle className="w-4 h-4 text-red-400" />
        )
      ) : (
        <Plus className="w-4 h-4 text-zinc-500" />
      )}
      <span className={`text-[11px] ${
        isOver 
          ? isValid ? 'text-emerald-400' : 'text-red-400'
          : 'text-zinc-500'
      }`}>
        {label}
      </span>
    </div>
  );
}

/**
 * DropZone.ListItem - Zona de drop entre items de lista
 */
export function ListItemDropZone({
  id,
  index,
  data = {},
  isActive = true,
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: `${id}-insert-${index}`,
    data: { 
      type: 'list-insert',
      index,
      ...data 
    },
    disabled: !isActive,
  });

  return (
    <div
      ref={setNodeRef}
      className={`
        h-1 my-0.5 rounded-full transition-all duration-150
        ${isOver 
          ? 'h-8 bg-indigo-500/20 ring-1 ring-indigo-500/30' 
          : 'bg-transparent hover:bg-white/[0.02]'
        }
      `}
    />
  );
}

export default DropZone;
