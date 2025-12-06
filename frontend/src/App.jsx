import React, { useState } from 'react';
import FileUpload from './components/FileUpload';
import MapView from './components/MapView';

function App() {
  const [routes, setRoutes] = useState([]);
  const [schedule, setSchedule] = useState([]);
  const [optimizing, setOptimizing] = useState(false);
  const [showMap, setShowMap] = useState(false);

  const handleUploadSuccess = (data) => {
    console.log("Routes loaded:", data);
    setRoutes(data);
    setSchedule([]); // Reset schedule on new upload
    setShowMap(false);
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
    <div className="h-screen w-screen bg-slate-900 text-slate-100 font-sans overflow-hidden flex flex-col">
      {/* Header */}
      <header className="relative z-20 border-b border-slate-800/60 bg-slate-900/90 backdrop-blur-xl flex-none">
        <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8 py-3 flex justify-between items-center">
          <div className="flex items-center space-x-3 group cursor-pointer">
            <div className="bg-gradient-to-br from-indigo-500 to-purple-600 p-2 rounded-lg shadow-lg shadow-indigo-500/20">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
              </svg>
            </div>
            <h1 className="text-xl font-bold tracking-tight">
              <span className="text-white">Tutti</span>
              <span className="text-slate-500 mx-2">|</span>
              <span className="text-sm font-medium text-indigo-400 uppercase tracking-wider">Cond'bus</span>
            </h1>
          </div>

          <div className="flex items-center gap-4">
            {!showMap && routes.length > 0 && (
              <button
                onClick={handleOptimize}
                disabled={optimizing}
                className={`px-4 py-2 text-sm font-bold text-white transition-all duration-200 bg-indigo-600 rounded-lg hover:bg-indigo-500 ${optimizing ? 'opacity-75 cursor-not-allowed' : ''}`}
              >
                {optimizing ? 'Optimizing...' : 'Run Optimization'}
              </button>
            )}
            {showMap && (
              <div className="flex gap-2">
                <button
                  onClick={handleExportPdf}
                  className="px-4 py-2 text-sm font-bold text-white bg-emerald-600 rounded-lg hover:bg-emerald-500 shadow-lg shadow-emerald-500/20 transition-all"
                >
                  Export PDF
                </button>
                <button
                  onClick={() => setShowMap(false)}
                  className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800 rounded-lg"
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
                  <span className="bg-clip-text text-transparent bg-gradient-to-r from-white via-slate-200 to-slate-400">
                    Optimize Your Fleet
                  </span>
                </h2>
                <p className="text-lg text-slate-400">
                  Intelligent routing with real-world traffic data.
                </p>
              </div>

              <div className="bg-slate-800/30 backdrop-blur-sm rounded-2xl border border-slate-700/50 p-8 shadow-xl mb-8">
                <FileUpload onUploadSuccess={handleUploadSuccess} />
              </div>

              {routes.length > 0 && (
                <div className="text-center">
                  <p className="text-slate-400 mb-4">{routes.length} contracts loaded</p>
                  <button
                    onClick={handleOptimize}
                    disabled={optimizing}
                    className="px-8 py-3 text-base font-bold text-white bg-indigo-600 rounded-xl hover:bg-indigo-500 transition-all shadow-lg shadow-indigo-500/25"
                  >
                    {optimizing ? 'Processing...' : 'Run Optimization'}
                  </button>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="h-full w-full relative animate-in fade-in duration-500">
            <MapView routes={routes} schedule={schedule} />
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
