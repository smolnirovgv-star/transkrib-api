import { useEffect, useRef, useState, useCallback } from 'react';
import { api } from '../services/api';

export interface TaskProgress {
  step: string;
  progress: number;
  status: 'pending' | 'running' | 'completed' | 'error';
  message?: string;
}

interface UseWebSocketOptions {
  taskId: string | null;
  onComplete?: () => void;
  onError?: (error: string) => void;
}

export function useWebSocket({ taskId, onComplete, onError }: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const [progress, setProgress] = useState<TaskProgress>({
    step: '',
    progress: 0,
    status: 'pending',
  });
  const [isConnected, setIsConnected] = useState(false);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;

  const cleanup = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const connect = useCallback(async () => {
    if (!taskId) return;

    cleanup();

    try {
      const wsUrl = await api.getWsUrl(taskId);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
      };

      ws.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data) as TaskProgress;
          setProgress(data);

          if (data.status === 'completed') {
            onComplete?.();
          } else if (data.status === 'error') {
            onError?.(data.message || 'Unknown error');
          }
        } catch {
          // Ignore malformed messages
        }
      };

      ws.onerror = () => {
        setIsConnected(false);
      };

      ws.onclose = () => {
        setIsConnected(false);

        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 10000);
          reconnectAttemptsRef.current += 1;
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        }
      };
    } catch {
      setIsConnected(false);
    }
  }, [taskId, cleanup, onComplete, onError]);

  useEffect(() => {
    if (taskId) {
      connect();
    }
    return cleanup;
  }, [taskId, connect, cleanup]);

  return { progress, isConnected };
}
