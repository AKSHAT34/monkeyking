type ToastType = 'success' | 'error' | 'warning' | 'info';

interface ToastEvent {
  type: ToastType;
  message: string;
  duration?: number;
}

type ToastListener = (event: ToastEvent) => void;
type ConnectionListener = (offline: boolean) => void;

const toastListeners = new Set<ToastListener>();
const connectionListeners = new Set<ConnectionListener>();

export const toastEvents = {
  subscribe(listener: ToastListener) {
    toastListeners.add(listener);
    return () => { toastListeners.delete(listener); };
  },
  emit(event: ToastEvent) {
    toastListeners.forEach((fn) => fn(event));
  },
};

export const connectionStatus = {
  subscribe(listener: ConnectionListener) {
    connectionListeners.add(listener);
    return () => { connectionListeners.delete(listener); };
  },
  setOffline(offline: boolean) {
    connectionListeners.forEach((fn) => fn(offline));
  },
};
