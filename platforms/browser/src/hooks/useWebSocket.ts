import { useState, useEffect, useRef, useCallback } from 'react';
import type { ProgressUpdate } from '../services/api';

interface WebSocketState {
  state: string;
  progress: number;
  message: string;
  step: string;
  resultFilename: string | null;
  error: string | null;
  isConnected: boolean;
}

const INITIAL_RECONNECT_DELAY = 1000;
const MAX_RECONNECT_DELAY = 30000;
const BACKOFF_MULTIPLIER = 2;

export function useWebSocket(taskId: string | null): WebSocketState {
  const [state, setState] = useState<string>('');
  const [progress, setProgress] = useState<number>(0);
  const [message, setMessage] = useState<string>('');
  const [step, setStep] = useState<string>('');
  const [resultFilename, setResultFilename] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectDelayRef = useRef<number>(INITIAL_RECONNECT_DELAY);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef<boolean>(true);
  const taskIdRef = useRef<string | null>(taskId);

  taskIdRef.current = taskId;

  const cleanup = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const connect = useCallback(
    (id: string) => {
      cleanup();

      if (!mountedRef.current) return;

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/tasks/${id}/progress`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setIsConnected(true);
        reconnectDelayRef.current = INITIAL_RECONNECT_DELAY;
      };

      ws.onmessage = (event: MessageEvent) => {
        if (!mountedRef.current) return;

        try {
          const data: ProgressUpdate = JSON.parse(event.data);
          setState(data.state);
          setProgress(data.progress);
          setMessage(data.message);
          setStep(data.step);
          setResultFilename(data.result_filename);
          setError(data.error);
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        setIsConnected(false);

        if (taskIdRef.current === id) {
          const delay = reconnectDelayRef.current;
          reconnectDelayRef.current = Math.min(
            delay * BACKOFF_MULTIPLIER,
            MAX_RECONNECT_DELAY
          );
          reconnectTimerRef.current = setTimeout(() => {
            if (mountedRef.current && taskIdRef.current === id) {
              connect(id);
            }
          }, delay);
        }
      };

      ws.onerror = () => {
        if (!mountedRef.current) return;
        ws.close();
      };
    },
    [cleanup]
  );

  useEffect(() => {
    mountedRef.current = true;

    if (taskId) {
      setState('');
      setProgress(0);
      setMessage('');
      setStep('');
      setResultFilename(null);
      setError(null);
      reconnectDelayRef.current = INITIAL_RECONNECT_DELAY;
      connect(taskId);
    } else {
      cleanup();
      setIsConnected(false);
    }

    return () => {
      mountedRef.current = false;
      cleanup();
    };
  }, [taskId, connect, cleanup]);

  return { state, progress, message, step, resultFilename, error, isConnected };
}
