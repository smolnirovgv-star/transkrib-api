import { motion } from 'framer-motion';
import { CheckCircle } from 'lucide-react';
import { useTranslation } from '../i18n';

interface ProgressBarProps {
  state: string;
  progress: number;
}

interface StepDefinition {
  key: string;
  labelKey: 'stepDownload' | 'stepConvert' | 'stepTranscribe' | 'stepAnalyze' | 'stepAssemble';
}

const STEPS: StepDefinition[] = [
  { key: 'downloading', labelKey: 'stepDownload' },
  { key: 'converting', labelKey: 'stepConvert' },
  { key: 'transcribing', labelKey: 'stepTranscribe' },
  { key: 'analyzing', labelKey: 'stepAnalyze' },
  { key: 'assembling', labelKey: 'stepAssemble' },
];

function getActiveStepIndex(state: string): number {
  const idx = STEPS.findIndex((s) => s.key === state);
  if (state === 'completed') return STEPS.length;
  return idx >= 0 ? idx : 0;
}

export function ProgressBar({ state, progress }: ProgressBarProps) {
  const { t } = useTranslation();
  const activeStepIndex = getActiveStepIndex(state);
  const clampedProgress = Math.min(100, Math.max(0, progress));

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      style={{
        maxWidth: '580px',
        width: '100%',
        margin: '32px auto 0',
        padding: '0 16px',
      }}
    >
      <div
        style={{
          background: 'rgba(255, 255, 255, 0.06)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '20px',
          padding: '28px 32px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.2)',
        }}
      >
        {/* Overall progress bar */}
        <div
          style={{
            position: 'relative',
            height: '6px',
            background: 'rgba(255, 255, 255, 0.08)',
            borderRadius: '3px',
            marginBottom: '24px',
            overflow: 'hidden',
          }}
        >
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${clampedProgress}%` }}
            transition={{ duration: 0.4, ease: 'easeOut' }}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              height: '100%',
              borderRadius: '3px',
              background: 'linear-gradient(90deg, #6C63FF, #FF6584, #6C63FF)',
              backgroundSize: '200% 100%',
              animation: 'progressGradient 2s linear infinite',
            }}
          />
        </div>

        {/* Steps */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}
        >
          {STEPS.map((step, index) => {
            const isCompleted = index < activeStepIndex;
            const isActive = index === activeStepIndex;

            return (
              <div
                key={step.key}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                }}
              >
                {/* Step indicator */}
                <div
                  style={{
                    width: '28px',
                    height: '28px',
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    background: isCompleted
                      ? 'linear-gradient(135deg, #6C63FF, #8B7DFF)'
                      : isActive
                        ? 'rgba(108, 99, 255, 0.2)'
                        : 'rgba(255, 255, 255, 0.05)',
                    border: isActive
                      ? '2px solid #6C63FF'
                      : '2px solid transparent',
                    transition: 'all 0.3s ease',
                  }}
                >
                  {isCompleted ? (
                    <CheckCircle size={16} color="#fff" />
                  ) : (
                    <span
                      style={{
                        fontSize: '12px',
                        fontWeight: 600,
                        color: isActive ? '#6C63FF' : 'rgba(255, 255, 255, 0.3)',
                      }}
                    >
                      {index + 1}
                    </span>
                  )}
                </div>

                {/* Step label */}
                <span
                  style={{
                    flex: 1,
                    fontSize: '14px',
                    fontWeight: isActive ? 600 : 400,
                    color: isCompleted
                      ? 'rgba(255, 255, 255, 0.8)'
                      : isActive
                        ? '#fff'
                        : 'rgba(255, 255, 255, 0.35)',
                    transition: 'all 0.3s ease',
                  }}
                >
                  {t(step.labelKey)}
                </span>

                {/* Active step animated bar */}
                {isActive && (
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: '60px' }}
                    style={{
                      height: '3px',
                      borderRadius: '2px',
                      background: 'linear-gradient(90deg, #6C63FF, #FF6584)',
                      flexShrink: 0,
                    }}
                  />
                )}
              </div>
            );
          })}
        </div>

        {/* Percentage display */}
        <div
          style={{
            textAlign: 'center',
            marginTop: '20px',
            fontSize: '28px',
            fontWeight: 700,
            background: 'linear-gradient(135deg, #6C63FF, #FF6584)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
          }}
        >
          {Math.round(clampedProgress)}%
        </div>
      </div>

      <style>{`
        @keyframes progressGradient {
          0% { background-position: 0% 0%; }
          100% { background-position: 200% 0%; }
        }
      `}</style>
    </motion.div>
  );
}
