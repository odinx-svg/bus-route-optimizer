import React, { useState } from 'react';
import FileUpload from './components/FileUpload';
import MapView from './components/MapView';
import DataPreviewModal from './components/DataPreviewModal';
import { GlassCard, NeonButton } from './components/ui';
import { MetricsSidebar } from './components/metrics';

function App() {
  const [routes, setRoutes] = useState([]);
  const [schedule, setSchedule] = useState([]);
  const [optimizing, setOptimizing] = useState(false);
  const [showMap, setShowMap] = useState(false);

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
    setSchedule([]); // Reset schedule
    setShowPreview(false);
    // Optional: Auto-run optimization? No, let user click button.
  };

  const handleCancelPreview = () => {
    setPreviewRoutes([]);
    setShowPreview(false);
  };

  const handleOptimize = async () => {
    if (routes.length === 0) return;
    setOptimizing(true);
    try {
      // Use the new LP optimizer for "real and reliable" results
      const response = await fetch('http://localhost:8000/optimize_lp', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(routes),
      });

      if (!response.ok) throw new Error('Optimization failed');

      const data = await response.json();
      setSchedule(data);
      setShowMap(true); // Auto-show map on success
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
        headers: {
          'Content-Type': 'application/json',
        },
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

  return (
    <div className="h-screen w-screen bg-dark-bg text-slate-100 font-sans overflow-hidden flex flex-col">
      {/* Header */}
      <header className="relative z-20 border-b border-glass-border bg-dark-bg/90 backdrop-blur-xl flex-none">
        <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8 py-3 flex justify-between items-center">
          <div className="flex items-center space-x-3 group cursor-pointer">
            <div className="bg-gradient-to-br from-neon-green/80 to-cyan-blue p-2 rounded-lg shadow-lg shadow-neon-green/20">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
              </svg>
            </div>
            <h1 className="text-xl font-bold tracking-tight">
              <span className="text-white">Tutti</span>
              <span className="text-slate-500 mx-2">|</span>
              <span className="text-sm font-medium text-neon-green uppercase tracking-wider">Cond'bus</span>
            </h1>
          </div>

          <div className="flex items-center gap-4">
            {!showMap && routes.length > 0 && (
              <NeonButton
                onClick={handleOptimize}
                disabled={optimizing}
                variant="green"
              >
                {optimizing ? 'Optimizing...' : 'Run Optimization'}
              </NeonButton>
            )}
            {showMap && (
              <div className="flex gap-2">
                <NeonButton onClick={handleExportPdf} variant="cyan">
                  Export PDF
                </NeonButton>
                <button
                  onClick={() => setShowMap(false)}
                  className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-glass-bg rounded-lg transition-all"
                >
                  Back to Upload
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1 relative overflow-hidden">
        {!showMap ? (
          <div className="h-full overflow-y-auto p-8">
            <div className="max-w-4xl mx-auto">
              <div className="text-center mb-12 mt-8">
                <h2 className="text-4xl md:text-5xl font-extrabold tracking-tight mb-4">
                  <span className="bg-clip-text text-transparent bg-gradient-to-r from-neon-green via-cyan-blue to-white">
                    Optimize Your Fleet
                  </span>
                </h2>
                <p className="text-lg text-slate-400">
                  Intelligent routing with real-world traffic data.
                </p>
              </div>

              <GlassCard className="p-8 mb-8">
                <FileUpload onUploadSuccess={handleUploadSuccess} />
              </GlassCard>

              {routes.length > 0 && (
                <div className="text-center">
                  <p className="text-slate-400 mb-4">{routes.length} contracts loaded</p>
                  <NeonButton
                    onClick={handleOptimize}
                    disabled={optimizing}
                    variant="green"
                    size="lg"
                  >
                    {optimizing ? 'Processing...' : 'Run Optimization'}
                  </NeonButton>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="h-full w-full relative flex">
            {/* Metrics Sidebar */}
            <div className="w-80 flex-shrink-0 h-full overflow-y-auto border-r border-glass-border bg-dark-bg/50 backdrop-blur-sm p-4">
              <MetricsSidebar schedule={schedule} />
            </div>
            {/* Map */}
            <div className="flex-1 relative animate-in fade-in duration-500">
              <MapView routes={routes} schedule={schedule} />
            </div>
          </div>
        )}
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
