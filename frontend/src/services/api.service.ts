/**
 * API Service - Cliente HTTP completo para Bus Route Optimizer
 * 
 * Proporciona métodos tipados para todos los endpoints de la API.
 * Incluye manejo de errores, interceptores y utilidades.
 * 
 * @module services/api
 * @version 1.0.0
 */

import type {
  WelcomeResponse,
  HealthResponse,
  Route,
  BusSchedule,
  ApiError,
  UploadProgress,
} from '../types/api';

// ============================================================================
// CONFIGURATION
// ============================================================================

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const DEFAULT_HEADERS: Record<string, string> = {
  'Accept': 'application/json',
};

// ============================================================================
// TYPES
// ============================================================================

interface RequestConfig extends RequestInit {
  params?: Record<string, string | number | boolean>;
}

interface ApiResponse<T> {
  data: T;
  status: number;
  headers: Headers;
}

interface UploadCallbacks {
  onProgress?: (progress: UploadProgress) => void;
  onComplete?: (routes: Route[]) => void;
  onError?: (error: ApiError) => void;
}

// ============================================================================
// HTTP CLIENT
// ============================================================================

/**
 * Cliente HTTP base con manejo de errores
 */
class HttpClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  /**
   * Construye URL completa con query params
   */
  private buildUrl(endpoint: string, params?: Record<string, string | number | boolean>): string {
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    const url = new URL(`${this.baseUrl}${cleanEndpoint}`);
    
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }
    
    return url.toString();
  }

  /**
   * Maneja la respuesta HTTP
   */
  private async handleResponse<T>(response: Response): Promise<ApiResponse<T>> {
    if (!response.ok) {
      const error = await this.parseError(response);
      throw error;
    }

    // Handle empty responses
    if (response.status === 204) {
      return { data: undefined as T, status: response.status, headers: response.headers };
    }

    // Handle blob responses (PDF)
    const contentType = response.headers.get('content-type');
    if (contentType?.includes('application/pdf')) {
      return { data: await response.blob() as T, status: response.status, headers: response.headers };
    }

    // Handle JSON responses
    const data = await response.json();
    return { data, status: response.status, headers: response.headers };
  }

  /**
   * Parsea errores de la API
   */
  private async parseError(response: Response): Promise<ApiError> {
    try {
      const body = await response.json();
      return {
        statusCode: response.status,
        detail: body.detail || body.message || 'Unknown error',
        timestamp: new Date().toISOString(),
        path: response.url,
      };
    } catch {
      return {
        statusCode: response.status,
        detail: response.statusText || 'Unknown error',
        timestamp: new Date().toISOString(),
        path: response.url,
      };
    }
  }

  /**
   * GET request
   */
  async get<T>(endpoint: string, config: RequestConfig = {}): Promise<ApiResponse<T>> {
    const url = this.buildUrl(endpoint, config.params);
    
    const response = await fetch(url, {
      ...config,
      method: 'GET',
      headers: {
        ...DEFAULT_HEADERS,
        ...config.headers,
      },
    });

    return this.handleResponse<T>(response);
  }

  /**
   * POST request
   */
  async post<T>(endpoint: string, body: unknown, config: RequestConfig = {}): Promise<ApiResponse<T>> {
    const url = this.buildUrl(endpoint, config.params);
    
    const isFormData = body instanceof FormData;
    
    const response = await fetch(url, {
      ...config,
      method: 'POST',
      headers: {
        ...DEFAULT_HEADERS,
        ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
        ...config.headers,
      },
      body: isFormData ? body : JSON.stringify(body),
    });

    return this.handleResponse<T>(response);
  }

  /**
   * PUT request
   */
  async put<T>(endpoint: string, body: unknown, config: RequestConfig = {}): Promise<ApiResponse<T>> {
    const url = this.buildUrl(endpoint, config.params);
    
    const response = await fetch(url, {
      ...config,
      method: 'PUT',
      headers: {
        ...DEFAULT_HEADERS,
        'Content-Type': 'application/json',
        ...config.headers,
      },
      body: JSON.stringify(body),
    });

    return this.handleResponse<T>(response);
  }

  /**
   * DELETE request
   */
  async delete<T>(endpoint: string, config: RequestConfig = {}): Promise<ApiResponse<T>> {
    const url = this.buildUrl(endpoint, config.params);
    
    const response = await fetch(url, {
      ...config,
      method: 'DELETE',
      headers: {
        ...DEFAULT_HEADERS,
        ...config.headers,
      },
    });

    return this.handleResponse<T>(response);
  }
}

// ============================================================================
// API SERVICE
// ============================================================================

const httpClient = new HttpClient(API_BASE_URL);

/**
 * Servicio API para Bus Route Optimizer
 */
export const apiService = {
  // -------------------------------------------------------------------------
  // BASIC ENDPOINTS
  // -------------------------------------------------------------------------

  /**
   * Verifica la salud del servicio
   * @returns Estado del servicio
   */
  async health(): Promise<HealthResponse> {
    const { data } = await httpClient.get<HealthResponse>('/health');
    return data;
  },

  /**
   * Obtiene mensaje de bienvenida
   * @returns Mensaje de bienvenida
   */
  async welcome(): Promise<WelcomeResponse> {
    const { data } = await httpClient.get<WelcomeResponse>('/');
    return data;
  },

  // -------------------------------------------------------------------------
  // ROUTES & UPLOAD
  // -------------------------------------------------------------------------

  /**
   * Sube archivos Excel con definiciones de rutas
   * 
   * @param files - Archivos Excel a subir
   * @param callbacks - Callbacks opcionales para progreso
   * @returns Rutas parseadas
   * 
   * @example
   * ```typescript
   * const input = document.getElementById('file-input') as HTMLInputElement;
   * const routes = await apiService.uploadFiles(input.files!, {
   *   onProgress: (p) => console.log(`${p.percentage}%`),
   * });
   * ```
   */
  async uploadFiles(
    files: FileList | File[],
    callbacks?: UploadCallbacks
  ): Promise<Route[]> {
    const fileArray = Array.from(files);
    
    // Simulate progress for each file
    if (callbacks?.onProgress) {
      fileArray.forEach((file, index) => {
        callbacks.onProgress!({
          filename: file.name,
          loaded: 0,
          total: file.size,
          percentage: 0,
          status: 'uploading',
        });
        
        // Simulate progress updates
        setTimeout(() => {
          callbacks.onProgress!({
            filename: file.name,
            loaded: file.size,
            total: file.size,
            percentage: 100,
            status: 'completed',
          });
        }, 500 * (index + 1));
      });
    }

    const formData = new FormData();
    fileArray.forEach((file) => {
      formData.append('files', file);
    });

    try {
      const { data } = await httpClient.post<Route[]>('/upload', formData);
      callbacks?.onComplete?.(data);
      return data;
    } catch (error) {
      callbacks?.onError?.(error as ApiError);
      throw error;
    }
  },

  // -------------------------------------------------------------------------
  // OPTIMIZATION
  // -------------------------------------------------------------------------

  /**
   * Ejecuta la optimización de rutas
   * 
   * @param routes - Rutas a optimizar
   * @returns Horarios de autobuses optimizados
   * 
   * @example
   * ```typescript
   * const schedule = await apiService.optimize(routes);
   * console.log(`Usando ${schedule.length} autobuses`);
   * ```
   */
  async optimize(routes: Route[]): Promise<BusSchedule[]> {
    const { data } = await httpClient.post<BusSchedule[]>('/optimize-lp', routes);
    return data;
  },

  /**
   * Ejecuta optimización con timeout personalizado
   * 
   * @param routes - Rutas a optimizar
   * @param timeoutMs - Timeout en milisegundos (default: 300000 = 5min)
   * @returns Horarios optimizados
   */
  async optimizeWithTimeout(
    routes: Route[],
    timeoutMs: number = 300000
  ): Promise<BusSchedule[]> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const { data } = await httpClient.post<BusSchedule[]>('/optimize-lp', routes, {
        signal: controller.signal,
      });
      return data;
    } finally {
      clearTimeout(timeoutId);
    }
  },

  // -------------------------------------------------------------------------
  // EXPORT
  // -------------------------------------------------------------------------

  /**
   * Exporta el horario a PDF
   * 
   * @param schedule - Horario a exportar
   * @returns Blob del PDF
   * 
   * @example
   * ```typescript
   * const pdfBlob = await apiService.exportPdf(schedule);
   * const url = URL.createObjectURL(pdfBlob);
   * window.open(url);
   * ```
   */
  async exportPdf(schedule: BusSchedule[]): Promise<Blob> {
    const { data } = await httpClient.post<Blob>('/export_pdf', schedule);
    return data;
  },

  /**
   * Exporta y descarga automáticamente el PDF
   * 
   * @param schedule - Horario a exportar
   * @param filename - Nombre del archivo (default: schedule.pdf)
   */
  async exportAndDownloadPdf(schedule: BusSchedule[], filename?: string): Promise<void> {
    const blob = await this.exportPdf(schedule);
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || 'schedule.pdf';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    
    URL.revokeObjectURL(url);
  },

  // -------------------------------------------------------------------------
  // FUTURE ENDPOINTS (Proposed API v2)
  // -------------------------------------------------------------------------

  /**
   * Obtiene métricas del dashboard (PROPUESTO - v2)
   * @requires Endpoint /metrics (no implementado)
   */
  async getMetrics(): Promise<unknown> {
    const { data } = await httpClient.get<unknown>('/metrics');
    return data;
  },

  /**
   * Valida rutas antes de optimizar (PROPUESTO - v2)
   * @requires Endpoint /validate (no implementado)
   */
  async validateRoutes(routes: Route[]): Promise<unknown> {
    const { data } = await httpClient.post<unknown>('/validate', { routes });
    return data;
  },

  // -------------------------------------------------------------------------
  // UTILITY METHODS
  // -------------------------------------------------------------------------

  /**
   * Verifica si el servicio está disponible
   * @returns true si el servicio responde correctamente
   */
  async isAvailable(): Promise<boolean> {
    try {
      await this.health();
      return true;
    } catch {
      return false;
    }
  },

  /**
   * Ejecuta el flujo completo: upload → optimize → export
   * 
   * @param files - Archivos Excel
   * @returns Objeto con rutas, horario y PDF blob
   */
  async fullWorkflow(files: FileList | File[]): Promise<{
    routes: Route[];
    schedule: BusSchedule[];
    pdfBlob: Blob;
  }> {
    const routes = await this.uploadFiles(files);
    const schedule = await this.optimize(routes);
    const pdfBlob = await this.exportPdf(schedule);
    
    return { routes, schedule, pdfBlob };
  },
};

// ============================================================================
// WEBSOCKET SERVICE (Proposed)
// ============================================================================

interface WebSocketCallbacks {
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  onProgress?: (progress: {
    phase: string;
    progress_percent: number;
    message: string;
  }) => void;
  onComplete?: (result: BusSchedule[]) => void;
}

/**
 * Servicio WebSocket para optimización con progreso (PROPUESTO - v2)
 */
export const wsService = {
  ws: null as WebSocket | null,

  /**
   * Conecta al WebSocket de optimización
   * @param callbacks - Handlers para eventos
   */
  connectOptimize(callbacks: WebSocketCallbacks): void {
    const wsUrl = API_BASE_URL.replace(/^http/, 'ws') + '/ws/optimize';
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => callbacks.onConnect?.();
    
    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      switch (message.type) {
        case 'progress':
          callbacks.onProgress?.(message);
          break;
        case 'completed':
          callbacks.onComplete?.(message.result);
          this.disconnect();
          break;
        case 'error':
          callbacks.onError?.(new Event(message.error.message));
          this.disconnect();
          break;
      }
    };

    this.ws.onclose = () => callbacks.onDisconnect?.();
    this.ws.onerror = (error) => callbacks.onError?.(error);
  },

  /**
   * Envía rutas para optimizar vía WebSocket
   * @param routes - Rutas a optimizar
   */
  sendRoutes(routes: Route[]): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'optimize', routes }));
    }
  },

  /**
   * Desconecta el WebSocket
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  },
};

// ============================================================================
// HOOKS REACT (Opcional)
// ============================================================================

/**
 * Hook para usar el API service en componentes React
 * 
 * @example
 * ```typescript
 * const { uploadFiles, optimize, isLoading, error } = useApi();
 * ```
 */
export function createApiHooks() {
  // Esto se implementaría con React hooks (useState, useCallback)
  // Se deja como referencia para implementación futura
  return {
    useUpload: () => ({ /* ... */ }),
    useOptimize: () => ({ /* ... */ }),
    useExport: () => ({ /* ... */ }),
  };
}

// ============================================================================
// EXPORTS
// ============================================================================

export { httpClient };
export type { RequestConfig, ApiResponse, UploadCallbacks, WebSocketCallbacks };

export default apiService;
