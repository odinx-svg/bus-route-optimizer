/**
 * Servicio de notificaciones con Sileo.
 *
 * Reemplaza alert() nativos por toasts modernos y no intrusivos.
 * @module services/notifications
 * @version 1.1.0
 */

import type { ReactNode } from 'react';
import { sileo } from 'sileo';

interface ToastOptions {
  description?: string | ReactNode;
  duration?: number;
  id?: string;
}

type ToastKind = 'success' | 'error' | 'info' | 'warning';

const DEFAULT_DURATION: Record<ToastKind, number> = {
  success: 4000,
  error: 6000,
  info: 4000,
  warning: 5000,
};

const showTypedToast = (
  type: ToastKind,
  message: string,
  options: ToastOptions = {}
): string => {
  const method = sileo[type];
  return method({
    title: message,
    description: options.description,
    duration: options.duration ?? DEFAULT_DURATION[type],
    id: options.id,
  } as any);
};

export const notifications = {
  success: (message: string, description?: string, duration = DEFAULT_DURATION.success): string =>
    showTypedToast('success', message, { description, duration }),

  error: (message: string, description?: string, duration = DEFAULT_DURATION.error): string =>
    showTypedToast('error', message, { description, duration }),

  info: (message: string, description?: string, duration = DEFAULT_DURATION.info): string =>
    showTypedToast('info', message, { description, duration }),

  warning: (message: string, description?: string, duration = DEFAULT_DURATION.warning): string =>
    showTypedToast('warning', message, { description, duration }),

  loading: (message: string): string => {
    // `state` existe en runtime de sileo aunque no este tipado en SileoOptions.
    return sileo.show({
      title: message,
      duration: null,
      ...( { state: 'loading' } as any ),
    } as any);
  },

  dismiss: (toastId: string): void => {
    sileo.dismiss(toastId);
  },

  dismissAll: (): void => {
    sileo.clear();
  },

  update: (
    toastId: string,
    type: ToastKind,
    message: string,
    description?: string
  ): void => {
    showTypedToast(type, message, {
      id: toastId,
      description,
      duration: type === 'error' ? DEFAULT_DURATION.error : DEFAULT_DURATION.success,
    });
  },

  promise: <T>(
    promise: Promise<T>,
    messages: {
      loading: string;
      success: string;
      error: string;
    }
  ): Promise<T> => {
    return sileo.promise(promise, {
      loading: {
        title: messages.loading,
      },
      success: {
        title: messages.success,
      },
      error: {
        title: messages.error,
      },
    });
  },
};

export const useNotifications = () => notifications;

export default notifications;
