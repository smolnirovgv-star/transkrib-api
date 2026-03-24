import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../services/api';
import { useWebSocket } from './useWebSocket';

interface TaskProgressState {
  state: string;
  progress: number;
  step: string;
  message: string;
  resultFilename: string | null;
  error: string | null;
}

const POLL_INTERVAL = 2000;

export function useTaskProgress(taskId: string | null): TaskProgressState {
  const ws = useWebSocket(taskId);

  const [restState, setRestState] = useState<string>('');
  const [restProgress, setRestProgress] = useState<number>(0);
  const [restStep, setRestStep] = useState<string>('');
  const [restMessage, setRestMessage] = useState<string>('');
  const [restResultFilename, setRestResultFilename] = useState<string | null>(null);
  const [restError, setRestError] = useState<string | null>(null);

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef<boolean>(true);

  const pollStatus = useCallback(async () => {
    if (!taskId || !mountedRef.current) return;

    try {
      const status = await api.getTaskStatus(taskId);
      if (!mountedRef.current) return;

      setRestState(status.state);
      setRestProgress(status.progress);
      setRestStep(status.step);
      setRestMessage(status.message);
      setRestResultFilename(status.result_filename);
      setRestError(status.error);

      if (status.state === 'completed' || status.state === 'error') {
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
      }
    } catch {
      // Silently ignore poll errors; will retry on next interval
    }
  }, [taskId]);

  useEffect(() => {
    mountedRef.current = true;

    if (!taskId) {
      setRestState('');
      setRestProgress(0);
      setRestStep('');
      setRestMessage('');
      setRestResultFilename(null);
      setRestError(null);
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      return;
    }

    // Always do an initial poll
    pollStatus();

    return () => {
      mountedRef.current = false;
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [taskId, pollStatus]);

  // Start/stop polling based on WebSocket connection status
  useEffect(() => {
    if (!taskId) return;

    if (!ws.isConnected) {
      // WebSocket disconnected -- start REST polling as fallback
      if (!pollingRef.current) {
        pollingRef.current = setInterval(pollStatus, POLL_INTERVAL);
      }
    } else {
      // WebSocket connected -- stop polling
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    }

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [taskId, ws.isConnected, pollStatus]);

  // Prefer WebSocket data when connected, otherwise use REST data
  if (ws.isConnected && ws.state) {
    return {
      state: ws.state,
      progress: ws.progress,
      step: ws.step,
      message: ws.message,
      resultFilename: ws.resultFilename,
      error: ws.error,
    };
  }

  return {
    state: restState,
    progress: restProgress,
    step: restStep,
    message: restMessage,
    resultFilename: restResultFilename,
    error: restError,
  };
}
