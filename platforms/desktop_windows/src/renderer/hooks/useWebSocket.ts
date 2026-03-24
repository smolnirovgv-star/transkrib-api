import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../services/api';

interface ProgressUpdate {
  task_id: string;
  state: string;
  step: string;
  progress: number;
  message: string;
  error_message?: string;
  timestamp: string;
}

export function useWebSocket(taskId: string | null) {
  const [data, setData] = useState<ProgressUpdate | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);

  const connect = useCallback(() => {
    if (!taskId) return;
    const url = api.getWsUrl(taskId);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => { setIsConnected(true); retriesRef.current = 0; };
    ws.onmessage = (e) => {
      try { setData(JSON.parse(e.data)); } catch {}
    };
    ws.onclose = () => {
      setIsConnected(false);
      if (retriesRef.current < 5) {
        retriesRef.current++;
        setTimeout(connect, Math.min(1000 * 2 ** retriesRef.current, 10000));
      }
    };
    ws.onerror = () => ws.close();
  }, [taskId]);

  useEffect(() => {
    connect();
    return () => { wsRef.current?.close(); };
  }, [connect]);

  return {
    state: data?.state ?? null,
    progress: data?.progress ?? 0,
    message: data?.message ?? '',
    step: data?.step ?? null,
    errorMessage: data?.error_message ?? null,
    isConnected,
  };
}
