/**
 * ManualScheduleEditor - DEPRECATED
 * 
 * Este componente ha sido consolidado en UnifiedWorkspace.
 * La funcionalidad de constructor manual ahora está integrada en UnifiedWorkspace.
 * 
 * @deprecated Usar UnifiedWorkspace desde '../workspace/UnifiedWorkspace'
 */

import React from 'react';
import { AlertTriangle } from 'lucide-react';

export function ManualScheduleEditor(props) {
  console.warn('[DEPRECATED] ManualScheduleEditor está obsoleto. Usa UnifiedWorkspace.');
  
  return (
    <div className="h-full flex flex-col items-center justify-center bg-gray-900 text-gray-400 p-8">
      <AlertTriangle className="w-12 h-12 text-amber-500 mb-4" />
      <h2 className="text-lg font-semibold text-white mb-2">Componente Obsoleto</h2>
      <p className="text-sm text-center max-w-md">
        ManualScheduleEditor ha sido consolidado en <strong>UnifiedWorkspace</strong>.
        <br />
        Usa <code>UnifiedWorkspace</code> con <code>mode=&quot;create&quot;</code>.
      </p>
    </div>
  );
}

export function ManualScheduleEditorSkeleton() {
  return (
    <div className="flex flex-col h-full gap-4 p-4 bg-gray-900">
      <div className="h-14 bg-gray-800 rounded-xl animate-pulse" />
      <div className="flex flex-1 gap-4">
        <div className="w-72 bg-gray-800 rounded-xl animate-pulse" />
        <div className="flex-1 space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-20 bg-gray-800 rounded-xl animate-pulse" />
          ))}
        </div>
      </div>
    </div>
  );
}

export default ManualScheduleEditor;
