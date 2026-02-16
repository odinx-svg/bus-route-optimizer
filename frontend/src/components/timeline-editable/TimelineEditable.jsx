/**
 * TimelineEditable - DEPRECATED
 * 
 * Este componente ha sido consolidado en UnifiedWorkspace.
 * Usar UnifiedWorkspace con mode='optimize' o mode='edit'.
 * 
 * @deprecated Usar UnifiedWorkspace desde '../workspace/UnifiedWorkspace'
 */

import React from 'react';
import { AlertTriangle } from 'lucide-react';

export function TimelineEditable(props) {
  console.warn('[DEPRECATED] TimelineEditable está obsoleto. Usa UnifiedWorkspace.');
  
  return (
    <div className="h-full flex flex-col items-center justify-center bg-[#0a0a0a] text-gray-400 p-8">
      <AlertTriangle className="w-12 h-12 text-amber-500 mb-4" />
      <h2 className="text-lg font-semibold text-white mb-2">Componente Obsoleto</h2>
      <p className="text-sm text-center max-w-md">
        TimelineEditable ha sido consolidado en <strong>UnifiedWorkspace</strong>.
        <br />
        Usa <code>UnifiedWorkspace</code> con <code>mode=&quot;optimize&quot;</code> o <code>mode=&quot;edit&quot;</code>.
      </p>
    </div>
  );
}

export default TimelineEditable;
