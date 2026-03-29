import React, { useEffect, useRef, useState } from 'react';
import { TitleBar } from './TitleBar';

const POLL_INTERVAL = 1500;

interface Props {
  onReady: () => void;
}

export const BackendStartup: React.FC<Props> = ({ onReady }) => {
  const isDev = (
    new URLSearchParams(window.location.search).get('dev') === 'true' ||
    localStorage.getItem('transkrib_dev_mode') === 'true' ||
    typeof (window as any).electronAPI === 'undefined'
  );

  const [elapsed, setElapsed] = useState(0);
  const [showSlowMessage, setShowSlowMessage] = useState(false);
  const onReadyRef = useRef(onReady);
  const startTimeRef = useRef(Date.now());

  useEffect(() => { onReadyRef.current = onReady; }, [onReady]);

  useEffect(() => {
    const timer = setTimeout(() => setShowSlowMessage(true), 15000);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (isDev) {
      onReady();
      return;
    }

    let dead = false;
    let attempt = 0;

    const poll = async () => {
      if (dead) return;
      attempt++;
      const elapsedMs = Date.now() - startTimeRef.current;
      console.log('[BackendStartup] Poll #' + attempt + ' at ' + elapsedMs + 'ms');

      try {
        const ok: boolean = await (window as any).electronAPI.pollBackendHealth();
        console.log('[BackendStartup] Poll #' + attempt + ' result: ' + ok + ', dead=' + dead);

        if (ok && !dead) {
          console.log('[BackendStartup] Backend ready at ' + (Date.now() - startTimeRef.current) + 'ms');
          onReadyRef.current();
          return;
        }
      } catch (err) {
        console.error('[BackendStartup] Poll #' + attempt + ' error:', err);
      }

      if (dead) return;
      setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
      setTimeout(poll, POLL_INTERVAL);
    };

    poll();
    return () => { dead = true; };
  }, []);

  if (isDev) return null;

  const pct = Math.min(95, Math.round((elapsed / 30) * 100));

  return (
    <div className="app-shell">
      <TitleBar />
      <div className="backend-startup">
        <div className="backend-startup-spinner" />
        <p className="backend-startup-title">Загрузка...</p>
        <p className="backend-startup-sub">Инициализация AI-движка ({elapsed}с)</p>
        <div className="backend-startup-bar">
          <div className="backend-startup-bar-fill" style={{ width: pct + '%' }} />
        </div>
        {showSlowMessage && (
          <div style={{marginTop: 16, textAlign: 'center', color: '#888'}}>
            <p>⏳ Первый запуск: скачиваем AI-модель (~250 МБ)</p>
            <p>Это займёт 2–3 минуты только один раз.</p>
            <p>При следующих запусках всё будет быстро ⚡</p>
          </div>
        )}
      </div>
    </div>
  );
};
