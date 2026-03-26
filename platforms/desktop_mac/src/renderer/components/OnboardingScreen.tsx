import { useState, useEffect } from 'react';

const ONBOARDING_KEY = 'transkrib_onboarding_shown';

const DOWNLOAD_URL =
  'https://github.com/smolnirovgv-star/transkrib-api/releases/latest';

const SHARE_TEXT =
  'Попробуй Transkrib SmartCut AI — транскрибация и нарезка видео за минуты.\nСкачать для Windows, macOS, Linux: ' + DOWNLOAD_URL;

interface OnboardingScreenProps {
  onClose: () => void;
}

export function OnboardingScreen({ onClose }: OnboardingScreenProps) {
  const [copied, setCopied] = useState(false);

  const openLink = (url: string) => {
    if ((window as any).electronAPI?.openExternal) {
      (window as any).electronAPI.openExternal(url);
    } else {
      window.open(url, '_blank');
    }
  };

  const handleShare = async () => {
    try {
      await navigator.clipboard.writeText(SHARE_TEXT);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const el = document.createElement('textarea');
      el.value = SHARE_TEXT;
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleClose = () => {
    localStorage.setItem(ONBOARDING_KEY, 'true');
    onClose();
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(10, 10, 15, 0.97)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999,
      padding: '40px 24px',
    }}>
      <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 8, textAlign: 'center', color: '#fff' }}>
        Transkrib SmartCut AI
      </h1>
      <p style={{ fontSize: 16, opacity: 0.6, marginBottom: 48, textAlign: 'center', color: '#fff' }}>
        Добро пожаловать!
      </p>

      <div style={{
        background: 'rgba(255,255,255,0.05)',
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 12,
        padding: '24px 32px',
        marginBottom: 32,
        maxWidth: 500,
        width: '100%',
        textAlign: 'center',
      }}>
        <p style={{ fontSize: 14, opacity: 0.7, marginBottom: 20, color: '#fff' }}>
          Есть версии для других операционных систем:
        </p>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap', marginBottom: 20 }}>
          {[
            { label: 'Windows', ext: '.exe' },
            { label: 'macOS', ext: '.dmg' },
            { label: 'Linux', ext: '.AppImage' },
          ].map(({ label, ext }) => (
            <button
              key={label}
              onClick={() => openLink(DOWNLOAD_URL)}
              style={{
                padding: '8px 16px',
                background: 'rgba(91,95,239,0.15)',
                border: '1px solid rgba(91,95,239,0.4)',
                borderRadius: 8,
                color: '#a5a8ff',
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              {label} {ext}
            </button>
          ))}
        </div>

        <button
          onClick={handleShare}
          style={{
            padding: '10px 24px',
            background: copied ? 'rgba(34,197,94,0.15)' : 'rgba(255,255,255,0.08)',
            border: '1px solid ' + (copied ? 'rgba(34,197,94,0.4)' : 'rgba(255,255,255,0.15)'),
            borderRadius: 8,
            color: copied ? '#4ade80' : 'rgba(255,255,255,0.8)',
            fontSize: 14,
            cursor: 'pointer',
            transition: 'all 0.2s',
          }}
        >
          {copied ? '\u2713 Ссылка скопирована!' : '\uD83D\uDCE4 Поделиться с коллегой'}
        </button>
      </div>

      <button
        onClick={handleClose}
        style={{
          padding: '14px 48px',
          background: '#5b5fef',
          border: 'none',
          borderRadius: 10,
          color: '#fff',
          fontSize: 16,
          fontWeight: 600,
          cursor: 'pointer',
        }}
      >
        Начать работу →
      </button>
    </div>
  );
}

export function useOnboarding() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    const shown = localStorage.getItem(ONBOARDING_KEY);
    if (!shown) {
      setShow(true);
    }
  }, []);

  const close = () => setShow(false);

  return { show, close };
}
