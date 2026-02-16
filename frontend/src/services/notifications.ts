/**
 * Servicio de Notificaciones - Toast Notifications con Sonner
 * 
 * Proporciona métodos tipados para mostrar notificaciones modernas
 * reemplazando los alert() nativos del navegador.
 * 
 * @module services/notifications
 * @version 1.0.0
 */

import { toast } from 'sonner';

/**
 * Opciones para las notificaciones
 */
interface ToastOptions {
  description?: string;
  duration?: number;
  id?: string;
}

/**
 * Servicio de notificaciones con Sonner
 * 
 * Reemplaza alert() nativos por notificaciones modernas y no intrusivas
 */
export const notifications = {
  /**
   * Muestra una notificación de éxito
   * @param message - Mensaje principal
   * @param description - Descripción opcional
   * @param duration - Duración en ms (default: 4000)
   */
  success: (message: string, description?: string, duration: number = 4000): string => {
    return toast.success(message, { description, duration });
  },

  /**
   * Muestra una notificación de error
   * @param message - Mensaje principal
   * @param description - Descripción opcional
   * @param duration - Duración en ms (default: 6000)
   */
  error: (message: string, description?: string, duration: number = 6000): string => {
    return toast.error(message, { description, duration });
  },

  /**
   * Muestra una notificación informativa
   * @param message - Mensaje principal
   * @param description - Descripción opcional
   * @param duration - Duración en ms (default: 4000)
   */
  info: (message: string, description?: string, duration: number = 4000): string => {
    return toast.info(message, { description, duration });
  },

  /**
   * Muestra una notificación de advertencia
   * @param message - Mensaje principal
   * @param description - Descripción opcional
   * @param duration - Duración en ms (default: 5000)
   */
  warning: (message: string, description?: string, duration: number = 5000): string => {
    return toast.warning(message, { description, duration });
  },

  /**
   * Muestra un toast de carga (loading)
   * @param message - Mensaje de carga
   * @returns ID del toast para poder cerrarlo después
   */
  loading: (message: string): string => {
    return toast.loading(message);
  },

  /**
   * Cierra una notificación específica por su ID
   * @param toastId - ID del toast a cerrar
   */
  dismiss: (toastId: string): void => {
    toast.dismiss(toastId);
  },

  /**
   * Cierra todas las notificaciones
   */
  dismissAll: (): void => {
    toast.dismiss();
  },

  /**
   * Actualiza un toast de loading a success/error
   * @param toastId - ID del toast a actualizar
   * @param type - Tipo de notificación final
   * @param message - Nuevo mensaje
   * @param description - Nueva descripción
   */
  update: (
    toastId: string,
    type: 'success' | 'error' | 'info' | 'warning',
    message: string,
    description?: string
  ): void => {
    toast[type](message, { 
      id: toastId, 
      description,
      duration: type === 'error' ? 6000 : 4000 
    });
  },

  /**
   * Promise wrapper - Muestra loading hasta que la promesa se resuelva
   * @param promise - Promesa a esperar
   * @param messages - Mensajes para loading, success y error
   * @returns Resultado de la promesa
   */
  promise: <T>(
    promise: Promise<T>,
    messages: {
      loading: string;
      success: string;
      error: string;
    }
  ): Promise<T> => {
    return toast.promise(promise, {
      loading: messages.loading,
      success: messages.success,
      error: messages.error,
    });
  },
};

/**
 * Hook de conveniencia para usar en componentes React
 * Proporciona acceso directo a todas las funciones de notificación
 */
export const useNotifications = () => notifications;

export default notifications;
