import React, { useEffect, useRef, useState } from 'react';
import { Download, Mic, Brain, Film, Check } from 'lucide-react';

interface Props {
  state: string | null;
  progress: number;
  submittedUrl?: string;
}

const STAGES = [
  { key: 'downloading', label: 'Скачивание',    icon: Download, states: ['downloading', 'converting'] },
  { key: 'transcribing', label: 'Транскрибация', icon: Mic,      states: ['loading_model', 'transcribing'] },
  { key: 'analyzing',   label: 'Анализ',        icon: Brain,    states: ['analyzing'] },
  { key: 'assembling',  label: 'Сборка видео',  icon: Film,     states: ['assembling'] },
];

function getActiveStage(state: string | null): number {
  if (!state) return -1;
  for (let i = 0; i < STAGES.length; i++) {
    if (STAGES[i].states.includes(state)) return i;
  }
  if (state === 'completed') return STAGES.length;
  return -1;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60).toString().padStart(2, '0');
  const s = (seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

export const ProcessingProgress: React.FC<Props> = ({ state, progress, submittedUrl }) => {
  const activeIdx = getActiveStage(state);
  const [elapsed, setElapsed] = useState(0);
  const prevActiveIdx = useRef(-1);

  useEffect(() => {
    if (activeIdx !== prevActiveIdx.current) {
      setElapsed(0);
      prevActiveIdx.current = activeIdx;
    }
  }, [activeIdx]);

  useEffect(() => {
    if (activeIdx < 0 || activeIdx >= STAGES.length) return;
    const interval = setInterval(() => setElapsed(e => e + 1), 1000);
    return () => clearInterval(interval);
  }, [activeIdx]);

  return (
    <div className="proc-progress">
      {submittedUrl && (
        <div className="proc-url-display">
          <span className="proc-url-text">{submittedUrl}</span>
        </div>
      )}
      <div className="proc-stages">
        {STAGES.map((stage, idx) => {
          const done = idx < activeIdx;
          const active = idx === activeIdx;
          const Icon = stage.icon;
          return (
            <React.Fragment key={stage.key}>
              <div className={`proc-stage ${done ? 'done' : active ? 'active' : 'pending'}`}>
                <div className="proc-stage-icon">
                  {done ? <Check size={16} /> : <Icon size={16} />}
                </div>
                <span className="proc-stage-label">{stage.label}</span>
                {active && (
                  <>
                    <span className="proc-stage-pct">{Math.round(progress)}%</span>
                    <span className="proc-stage-timer">{formatTime(elapsed)}</span>
                    {stage.key === 'transcribing' && (
                      <div className="proc-wave">
                        <div className="proc-wave-bar" />
                        <div className="proc-wave-bar" />
                        <div className="proc-wave-bar" />
                        <div className="proc-wave-bar" />
                        <div className="proc-wave-bar" />
                      </div>
                    )}
                  </>
                )}
              </div>
              {idx < STAGES.length - 1 && (
                <div className={`proc-connector ${done ? 'done' : ''}`} />
              )}
            </React.Fragment>
          );
        })}
      </div>
      <div className="proc-bar-track">
        <div
          className="proc-bar-fill"
          style={{ width: `${Math.min(100, (activeIdx / (STAGES.length - 1)) * 100 + (progress / (STAGES.length - 1)))}%` }}
        />
      </div>
    </div>
  );
};
