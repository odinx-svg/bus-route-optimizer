import React from 'react';
import { AlertTriangle, RefreshCw, Home, Copy, Check } from 'lucide-react';

export class TimelineErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { 
      hasError: false, 
      error: null,
      errorInfo: null,
      copied: false,
      retryCount: 0
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    console.error('Timeline Error Boundary caught:', error, errorInfo);
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  handleRetry = () => {
    this.setState(prev => ({
      retryCount: prev.retryCount + 1,
      hasError: false,
      error: null,
      errorInfo: null
    }));
  };

  handleReload = () => window.location.reload();
  handleGoHome = () => window.location.href = '/';

  copyErrorDetails = () => {
    const { error, errorInfo } = this.state;
    const details = `Error: ${error?.message || 'Unknown'}\nTime: ${new Date().toISOString()}`.trim();
    navigator.clipboard.writeText(details).then(() => {
      this.setState({ copied: true });
      setTimeout(() => this.setState({ copied: false }), 2000);
    });
  };

  render() {
    const { hasError, error, copied, retryCount } = this.state;
    const { fallback, children, maxRetries = 3 } = this.props;

    if (!hasError) return children;
    if (fallback) return fallback(error, this.handleRetry);

    const isNetworkError = error?.message?.includes('network') || error?.message?.includes('fetch');

    return (
      <div className="min-h-[200px] flex items-center justify-center p-4">
        <div className="bg-red-900/20 border border-red-500/50 rounded-xl p-6 max-w-lg w-full">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center">
              <AlertTriangle className="w-6 h-6 text-red-400" />
            </div>
            <div>
              <h3 className="text-red-400 font-bold text-lg">
                {isNetworkError ? 'Error de conexión' : 'Algo salió mal'}
              </h3>
              <p className="text-red-300/60 text-sm">
                {retryCount > 0 ? `Reintento ${retryCount} de ${maxRetries}` : 'Error inesperado'}
              </p>
            </div>
          </div>

          <div className="bg-red-950/50 rounded-lg p-3 mb-4">
            <p className="text-red-200 text-sm font-mono break-all">{error?.message || 'Error desconocido'}</p>
          </div>

          <div className="flex flex-wrap gap-2">
            {retryCount < maxRetries ? (
              <button onClick={this.handleRetry} className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg text-sm font-medium">
                <RefreshCw className="w-4 h-4" /> Intentar de nuevo
              </button>
            ) : (
              <button onClick={this.handleReload} className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg text-sm font-medium">
                <RefreshCw className="w-4 h-4" /> Recargar
              </button>
            )}
            <button onClick={this.handleGoHome} className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-sm font-medium">
              <Home className="w-4 h-4" /> Ir al inicio
            </button>
            <button onClick={this.copyErrorDetails} className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm font-medium ml-auto">
              {copied ? <><Check className="w-4 h-4 text-green-400" /> Copiado</> : <><Copy className="w-4 h-4" /> Copiar</>}
            </button>
          </div>
        </div>
      </div>
    );
  }
}

export function SectionErrorBoundary({ children, sectionName, onReset }) {
  return (
    <TimelineErrorBoundary
      fallback={(error, retry) => (
        <div className="p-4 bg-amber-900/20 border border-amber-500/30 rounded-lg">
          <div className="flex items-center gap-2 text-amber-400 mb-2">
            <AlertTriangle className="w-4 h-4" />
            <span className="font-medium text-sm">Error en {sectionName}</span>
          </div>
          <p className="text-amber-300/60 text-xs mb-3">{error.message}</p>
          <button onClick={() => { retry(); onReset?.(); }} className="text-xs px-3 py-1 bg-amber-600/30 hover:bg-amber-600/50 text-amber-200 rounded">Reintentar</button>
        </div>
      )}
    >
      {children}
    </TimelineErrorBoundary>
  );
}

export function useErrorHandler() {
  const [error, setError] = React.useState(null);
  const handleError = React.useCallback((err) => { setError(err); console.error(err); }, []);
  const clearError = React.useCallback(() => setError(null), []);

  const ErrorDisplay = React.useCallback(({ onRetry }) => {
    if (!error) return null;
    return (
      <div className="p-4 bg-red-900/20 border border-red-500/50 rounded-lg animate-in fade-in">
        <div className="flex items-center gap-2 mb-2"><AlertTriangle className="w-5 h-5 text-red-400" /><span className="text-red-400 font-medium">Error</span></div>
        <p className="text-red-300/80 text-sm mb-3">{error.message}</p>
        <div className="flex gap-2">
          {onRetry && <button onClick={() => { clearError(); onRetry(); }} className="px-3 py-1.5 bg-red-600 text-white text-sm rounded">Reintentar</button>}
          <button onClick={clearError} className="px-3 py-1.5 bg-gray-700 text-white text-sm rounded">Cerrar</button>
        </div>
      </div>
    );
  }, [error, clearError]);

  return { error, handleError, clearError, ErrorDisplay };
}

export default TimelineErrorBoundary;
