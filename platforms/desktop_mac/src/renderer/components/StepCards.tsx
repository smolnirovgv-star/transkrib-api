import React from 'react';
import { ArrowDownToLine, FileAudio, Brain, Film, CheckCircle } from 'lucide-react';
import { useTranslation } from '../i18n';

const STEPS = [
  { key: 'steps.convert', icon: ArrowDownToLine, states: ['converting'] },
  { key: 'steps.transcribe', icon: FileAudio, states: ['loading_model', 'transcribing'] },
  { key: 'steps.analyze', icon: Brain, states: ['analyzing'] },
  { key: 'steps.assemble', icon: Film, states: ['assembling'] },
];

const STATE_ORDER = ['pending', 'downloading', 'converting', 'loading_model', 'transcribing', 'analyzing', 'assembling', 'completed'];

interface Props {
  currentState: string | null;
  progress: number;
}

export const StepCards: React.FC<Props> = ({ currentState, progress }) => {
  const { t } = useTranslation();
  const currentIdx = STATE_ORDER.indexOf(currentState || '');

  return (
    <div className="step-cards">
      {STEPS.map((step, i) => {
const lastStepIdx = STATE_ORDER.indexOf(step.states[step.states.length - 1]);
        const isActive = step.states.includes(currentState || '');
        const isDone = currentIdx > lastStepIdx;
        const Icon = isDone ? CheckCircle : step.icon;

        return (
          <div key={step.key} className={`step-card ${isActive ? 'active' : ''} ${isDone ? 'completed' : ''}`}>
            <div className="step-card-icon">
              <svg className="progress-ring" viewBox="0 0 40 40">
                <circle cx="20" cy="20" r="17" fill="none" stroke="var(--color-border-strong)" strokeWidth="3" />
                {isActive && (
                  <circle cx="20" cy="20" r="17" fill="none" stroke="var(--color-primary)" strokeWidth="3"
                    strokeDasharray={`${progress * 1.07} 107`}
                    strokeLinecap="round" transform="rotate(-90 20 20)" />
                )}
                {isDone && (
                  <circle cx="20" cy="20" r="17" fill="none" stroke="var(--color-success)" strokeWidth="3" />
                )}
              </svg>
              <Icon size={18} />
            </div>
            <span className="step-card-name">{t(step.key as any)}</span>
            {isActive && <span className="step-card-progress">{Math.round(progress)}%</span>}
          </div>
        );
      })}
    </div>
  );
};
