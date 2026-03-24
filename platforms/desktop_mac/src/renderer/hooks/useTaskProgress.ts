import { useState, useEffect } from 'react';

export function useTaskProgress(taskId: string | null) {
  const [state, setState] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [step, setStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!taskId) return;
    let cancelled = false;
    let pollCount = 0;

    const poll = async () => {
      if (cancelled) return;
      pollCount++;
      try {
        const s = await window.electronAPI.getTaskStatus(taskId);
        console.log(`[TaskProgress] poll #${pollCount} taskId=${taskId}`, s ? `state=${s.state} progress=${s.progress_percent}` : 'null');
        if (!cancelled && s) {
          setState(s.state);
          setProgress(s.progress_percent);
          setStep(s.state);
          setError(s.error_message || null);
        }
      } catch (e) {
        console.error(`[TaskProgress] poll #${pollCount} error:`, e);
      }
      if (!cancelled) setTimeout(poll, 1500);
    };

    poll();
    return () => { cancelled = true; };
  }, [taskId]);

  return { state, progress, step, error };
}
