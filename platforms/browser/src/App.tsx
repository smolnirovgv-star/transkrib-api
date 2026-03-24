import { useState, useCallback } from 'react';
import { AnimatePresence } from 'framer-motion';
import { useTranslation } from './i18n';
import { api } from './services/api';
import { useTaskProgress } from './hooks/useTaskProgress';
import { LanguageSelector } from './components/LanguageSelector';
import { Hero } from './components/Hero';
import { MainCard } from './components/MainCard';
import { ProgressBar } from './components/ProgressBar';
import { ResultsSection } from './components/ResultsSection';
import { Footer } from './components/Footer';

const ACTIVE_STATES = [
  'pending',
  'downloading',
  'converting',
  'transcribing',
  'analyzing',
  'assembling',
];

export function App() {
  const { t } = useTranslation();
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const taskProgress = useTaskProgress(currentTaskId);

  const isTaskActive =
    currentTaskId !== null && ACTIVE_STATES.includes(taskProgress.state);
  const isTaskCompleted =
    currentTaskId !== null && taskProgress.state === 'completed';
  const isTaskError =
    currentTaskId !== null && taskProgress.state === 'error';

  const handleFileSelected = useCallback(async (file: File) => {
    setIsUploading(true);
    setErrorMessage(null);

    try {
      const response = await api.uploadFile(file);
      setCurrentTaskId(response.task_id);
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : 'Upload failed'
      );
    } finally {
      setIsUploading(false);
    }
  }, []);

  const handleUrlSubmit = useCallback(async (url: string) => {
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const response = await api.submitUrl(url);
      setCurrentTaskId(response.task_id);
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : 'Submission failed'
      );
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  const handleReset = useCallback(() => {
    setCurrentTaskId(null);
    setErrorMessage(null);
  }, []);

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        position: 'relative',
      }}
    >
      {/* Background blobs */}
      <div
        style={{
          position: 'fixed',
          top: '-20%',
          left: '-10%',
          width: '500px',
          height: '500px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(108, 99, 255, 0.15), transparent 70%)',
          pointerEvents: 'none',
          filter: 'blur(60px)',
        }}
      />
      <div
        style={{
          position: 'fixed',
          bottom: '-15%',
          right: '-5%',
          width: '400px',
          height: '400px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255, 101, 132, 0.12), transparent 70%)',
          pointerEvents: 'none',
          filter: 'blur(60px)',
        }}
      />

      <LanguageSelector />

      <div
        style={{
          width: '100%',
          maxWidth: '720px',
          padding: '0 16px',
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Hero />

        {/* Show MainCard only when no active task */}
        {!isTaskActive && !isTaskCompleted && (
          <MainCard
            onFileSelected={handleFileSelected}
            onUrlSubmit={handleUrlSubmit}
            isUploading={isUploading}
            isSubmitting={isSubmitting}
          />
        )}

        {/* Error message */}
        <AnimatePresence>
          {(errorMessage || isTaskError) && (
            <div
              style={{
                maxWidth: '580px',
                width: '100%',
                margin: '20px auto 0',
                padding: '0 16px',
              }}
            >
              <div
                style={{
                  background: 'rgba(255, 101, 132, 0.1)',
                  border: '1px solid rgba(255, 101, 132, 0.3)',
                  borderRadius: '14px',
                  padding: '16px 20px',
                  color: '#FF6584',
                  fontSize: '14px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '12px',
                }}
              >
                <span>
                  {errorMessage || taskProgress.error || t('error')}
                </span>
                <button
                  onClick={handleReset}
                  style={{
                    padding: '6px 16px',
                    background: 'rgba(255, 101, 132, 0.2)',
                    border: '1px solid rgba(255, 101, 132, 0.4)',
                    borderRadius: '8px',
                    color: '#FF6584',
                    fontSize: '13px',
                    fontWeight: 600,
                    fontFamily: 'inherit',
                    cursor: 'pointer',
                    flexShrink: 0,
                  }}
                >
                  {t('retry')}
                </button>
              </div>
            </div>
          )}
        </AnimatePresence>

        {/* Progress display */}
        <AnimatePresence>
          {isTaskActive && (
            <ProgressBar
              state={taskProgress.state}
              progress={taskProgress.progress}
            />
          )}
        </AnimatePresence>

        {/* Results display */}
        <AnimatePresence>
          {isTaskCompleted && taskProgress.resultFilename && (
            <div>
              <ResultsSection resultFilename={taskProgress.resultFilename} />
              <div
                style={{
                  textAlign: 'center',
                  marginTop: '20px',
                }}
              >
                <button
                  onClick={handleReset}
                  style={{
                    padding: '10px 28px',
                    background: 'rgba(255, 255, 255, 0.08)',
                    border: '1px solid rgba(255, 255, 255, 0.12)',
                    borderRadius: '12px',
                    color: 'rgba(255, 255, 255, 0.7)',
                    fontSize: '14px',
                    fontWeight: 500,
                    fontFamily: 'inherit',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.12)';
                    e.currentTarget.style.color = '#fff';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)';
                    e.currentTarget.style.color = 'rgba(255, 255, 255, 0.7)';
                  }}
                >
                  {t('retry')}
                </button>
              </div>
            </div>
          )}
        </AnimatePresence>

        <div style={{ flex: 1 }} />

        <Footer />
      </div>
    </div>
  );
}
