import React, { useState, lazy, Suspense } from 'react';
import FileUpload from './components/FileUpload';
import MapView from './components/MapView';
import DataPreviewModal from './components/DataPreviewModal';
import { GlassCard, NeonButton } from './components/ui';
import { MetricsSidebar } from './components/metrics';

// Lazy load Globe for performance
const Globe3D = lazy(() => import('./components/Globe3D'));

function App() {
  const [routes, setRoutes] = useState([]);
  const [schedule, setSchedule] = useState([]);
  const [optimizing, setOptimizing] = useState(false);
  const [viewMode, setViewMode] = useState('globe'); // 'globe' | 'map'

  // Preview State
  const [previewRoutes, setPreviewRoutes] = useState([]);
  const [showPreview, setShowPreview] = useState(false);

  const handleUploadSuccess = (data) => {
    console.log("Routes loaded for preview:", data);
    setPreviewRoutes(data);
    setShowPreview(true);
  };

  const handleConfirmPreview = () => {
    setRoutes(previewRoutes);
    setSchedule([]);
    setShowPreview(false);
  };

  const handleCancelPreview = () => {
    setPreviewRoutes([]);
    setShowPreview(false);
  };

  const handleOptimize = async () => {
    if (routes.length === 0) return;
    setOptimizing(true);
    try {
      const response = await fetch('http://localhost:8000/optimize_lp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(routes),
      });

      if (!response.ok) throw new Error('Optimization failed');

      const data = await response.json();
      setSchedule(data);
    } catch (error) {
      console.error("Error optimizing:", error);
      alert("Failed to optimize routes");
    } finally {
      setOptimizing(false);
    }
  };

  const handleExportPdf = async () => {
    if (schedule.length === 0) return;
    try {
      const response = await fetch('http://localhost:8000/export_pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(schedule),
      });

      if (!response.ok) throw new Error('Export failed');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'tutti_schedule.pdf';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error("Error exporting PDF:", error);
      alert("Failed to export PDF");
    }
  };

  const hasData = routes.length > 0;

  return (
    <div className="h-screen w-screen bg-dark-bg text-slate-100 font-sans overflow-hidden flex flex-col">
      {/* Header */}
      <header className="relative z-30 border-b border-glass-border bg-dark-bg/80 backdrop-blur-xl flex-none">
        <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8 py-3 flex justify-between items-center">
          <div className="flex items-center space-x-3 group cursor-pointer">
            <div className="bg-gradient-to-br from-neon-green/80 to-cyan-blue p-2 rounded-lg shadow-lg shadow-neon-green/20">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h1 className="text-xl font-bold tracking-tight">
              <span className="text-white">Tutti</span>
              <span className="text-slate-500 mx-2">|</span>
              <span className="text-sm font-medium text-neon-green uppercase tracking-wider">Cond'bus</span>
            </h1>
          </div>

          <div className="flex items-center gap-3">
            {/* View toggle */}
            {hasData && (
              <div className="flex bg-glass-bg rounded-lg p-1 border border-glass-border">
                <button
                  onClick={() => setViewMode('globe')}
                  className={`px-3 py-1.5 text-sm font-medium rounded-md transition-all ${
                    viewMode === 'globe'
                      ? 'bg-neon-green/20 text-neon-green'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  🌍 Globe
                </button>
                <button
                  onClick={() => setViewMode('map')}
                  className={`px-3 py-1.5 text-sm font-medium rounded-md transition-all ${
                    viewMode === 'map'
                      ? 'bg-cyan-blue/20 text-cyan-blue'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  🗺️ Map
                </button>
              </div>
            )}

            {hasData && !schedule.length && (
              <NeonButton
                onClick={handleOptimize}
                disabled={optimizing}
                variant="green"
              >
                {optimizing ? 'Optimizing...' : 'Run Optimization'}
              </NeonButton>
            )}

            {schedule.length > 0 && (
              <NeonButton onClick={handleExportPdf} variant="cyan">
                Export PDF
              </NeonButton>
            )}
          </div>
        </div>
      </header>

      {/* Main Content - Globe as primary view */}
      <main className="flex-1 relative overflow-hidden">
        {/* 3D Globe Background - Always visible */}
        <div className="absolute inset-0 z-0">
          <Suspense fallback={
            <div className="w-full h-full flex items-center justify-center bg-dark-bg">
              <div className="text-neon-green animate-pulse text-xl">Loading Globe...</div>
            </div>
          }>
            <Globe3D routes={routes} />
          </Suspense>
        </div>

        {/* Overlay UI */}
        <div className="relative z-10 h-full flex">
          {/* Left Panel - Upload or Metrics */}
          <div className="w-96 h-full flex flex-col p-4 bg-gradient-to-r from-dark-bg via-dark-bg/95 to-transparent">
            {!hasData ? (
              /* Upload Panel */
              <div className="flex flex-col h-full justify-center">
                <div className="mb-8">
                  <h2 className="text-3xl font-bold mb-2">
                    <span className="bg-clip-text text-transparent bg-gradient-to-r from-neon-green to-cyan-blue">
                      Fleet Optimizer
                    </span>
                  </h2>
                  <p className="text-slate-400">
                    Upload your route data to visualize on the globe
                  </p>
                </div>

                <GlassCard className="p-6">
                  <FileUpload onUploadSuccess={handleUploadSuccess} />
                </GlassCard>
              </div>
            ) : (
              /* Metrics Panel */
              <div className="flex flex-col h-full">
                <div className="mb-4">
                  <h3 className="text-lg font-semibold text-neon-green mb-1">
                    {routes.length} Routes Loaded
                  </h3>
                  <p className="text-sm text-slate-400">
                    {schedule.length > 0 ? 'Optimization complete' : 'Ready to optimize'}
                  </p>
                </div>

                {schedule.length > 0 ? (
                  <div className="flex-1 overflow-y-auto">
                    <MetricsSidebar schedule={schedule} />
                  </div>
                ) : (
                  <GlassCard className="p-6 text-center">
                    <p className="text-slate-300 mb-4">
                      Click "Run Optimization" to process your routes
                    </p>
                    <NeonButton
                      onClick={handleOptimize}
                      disabled={optimizing}
                      variant="green"
                      size="lg"
                    >
                      {optimizing ? 'Processing...' : 'Run Optimization'}
                    </NeonButton>
                  </GlassCard>
                )}

                {/* New upload button */}
                <div className="mt-4 pt-4 border-t border-glass-border">
                  <button
                    onClick={() => {
                      setRoutes([]);
                      setSchedule([]);
                    }}
                    className="text-sm text-slate-400 hover:text-neon-green transition-colors"
                  >
                    ← Upload different file
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Right side - Map view (only when toggled) */}
          {hasData && viewMode === 'map' && (
            <div className="flex-1 relative">
              <GlassCard className="absolute inset-4 overflow-hidden">
                <MapView routes={routes} schedule={schedule} />
              </GlassCard>
            </div>
          )}
        </div>
      </main>

      {/* Preview Modal */}
      {showPreview && (
        <DataPreviewModal
          routes={previewRoutes}
          onConfirm={handleConfirmPreview}
          onCancel={handleCancelPreview}
        />
      )}
    </div>
  );
}

export default App;
