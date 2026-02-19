import React from 'react';
import { Inbox } from 'lucide-react';

export const EmptyState = ({ 
  icon: Icon = Inbox,
  title = 'No hay contenido',
  description = 'No se encontraron elementos para mostrar.',
  action = null,
  className = '' 
}) => (
  <div className={`flex flex-col items-center justify-center py-12 px-4 text-center ${className}`}>
    <div className="w-16 h-16 rounded-2xl bg-[#1a2d3f] border border-[#253a4f] flex items-center justify-center mb-4">
      <Icon className="w-8 h-8 text-gray-500" />
    </div>
    <h3 className="text-lg font-medium text-gray-200">{title}</h3>
    <p className="text-sm text-gray-500 mt-1 max-w-xs">{description}</p>
    {action && <div className="mt-6">{action}</div>}
  </div>
);
