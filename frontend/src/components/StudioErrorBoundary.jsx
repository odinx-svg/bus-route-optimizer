import React from 'react';
import { AlertTriangle, RefreshCcw } from 'lucide-react';

export default class StudioErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
    };
  }

  static getDerivedStateFromError(error) {
    return {
      hasError: true,
      error: error || null,
    };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[StudioErrorBoundary] render crash', {
      message: error?.message || String(error),
      stack: error?.stack || null,
      componentStack: errorInfo?.componentStack || null,
    });
  }

  componentDidUpdate(prevProps) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.hasError) {
      this.setState({ hasError: false, error: null });
    }
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <div className="h-full w-full flex items-center justify-center">
        <div className="max-w-xl w-full gt-panel rounded-2xl p-6 border border-rose-400/25 bg-rose-500/5 text-center space-y-3">
          <div className="mx-auto w-12 h-12 rounded-xl bg-rose-500/15 border border-rose-400/30 flex items-center justify-center">
            <AlertTriangle className="w-6 h-6 text-rose-300" />
          </div>
          <h3 className="text-lg font-semibold text-slate-100">Studio no pudo renderizarse</h3>
          <p className="text-sm text-slate-300">
            Se detecto un estado de datos no valido. Puedes volver a Control o reintentar.
          </p>
          {this.state.error?.message ? (
            <p className="text-xs text-rose-200/90 data-mono">{this.state.error.message}</p>
          ) : null}
          <div className="flex items-center justify-center gap-2 pt-1">
            <button
              type="button"
              onClick={() => this.props.onBackToControl?.()}
              className="px-3 py-2 rounded-lg text-xs font-semibold uppercase tracking-[0.08em] border border-slate-500/50 text-slate-200 hover:border-slate-300/60 hover:text-white transition-colors"
            >
              Volver a Control
            </button>
            <button
              type="button"
              onClick={this.handleRetry}
              className="px-3 py-2 rounded-lg text-xs font-semibold uppercase tracking-[0.08em] bg-gt-accent text-white hover:brightness-110 transition-colors inline-flex items-center gap-1.5"
            >
              <RefreshCcw className="w-3.5 h-3.5" />
              Reintentar
            </button>
          </div>
        </div>
      </div>
    );
  }
}
