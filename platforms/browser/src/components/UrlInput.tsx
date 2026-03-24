import React, { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Clipboard, Check, X, ArrowRight } from 'lucide-react';
import { useTranslation } from '../i18n';

interface UrlInputProps {
  onSubmit: (url: string) => void;
  isSubmitting: boolean;
}

function isValidUrl(value: string): boolean {
  if (!value.trim()) return false;
  try {
    const url = new URL(value.trim());
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

export function UrlInput({ onSubmit, isSubmitting }: UrlInputProps) {
  const { t } = useTranslation();
  const [url, setUrl] = useState('');
  const [touched, setTouched] = useState(false);

  const valid = isValidUrl(url);
  const showValidation = touched && url.length > 0;

  const handlePaste = useCallback(async () => {
    try {
      const text = await navigator.clipboard.readText();
      setUrl(text);
      setTouched(true);
    } catch {
      // Clipboard API not available or permission denied
    }
  }, []);

  const handleSubmit = useCallback(() => {
    if (valid && !isSubmitting) {
      onSubmit(url.trim());
    }
  }, [valid, isSubmitting, onSubmit, url]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') {
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          background: 'rgba(255, 255, 255, 0.05)',
          borderRadius: '14px',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          overflow: 'hidden',
          transition: 'border-color 0.2s ease',
          borderLeftWidth: '3px',
          borderLeftColor: showValidation
            ? valid
              ? '#4ade80'
              : '#FF6584'
            : '#6C63FF',
        }}
      >
        <input
          type="url"
          value={url}
          onChange={(e) => {
            setUrl(e.target.value);
            if (!touched) setTouched(true);
          }}
          onBlur={() => setTouched(true)}
          onKeyDown={handleKeyDown}
          placeholder={t('urlPlaceholder')}
          disabled={isSubmitting}
          style={{
            flex: 1,
            padding: '14px 16px',
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: '#fff',
            fontSize: '15px',
            fontFamily: 'inherit',
          }}
        />

        {showValidation && (
          <div
            style={{
              padding: '0 8px',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            {valid ? (
              <Check size={18} color="#4ade80" />
            ) : (
              <X size={18} color="#FF6584" />
            )}
          </div>
        )}

        <button
          onClick={handlePaste}
          title="Paste"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '14px 12px',
            background: 'transparent',
            border: 'none',
            borderLeft: '1px solid rgba(255, 255, 255, 0.08)',
            color: 'rgba(255, 255, 255, 0.5)',
            cursor: 'pointer',
            transition: 'color 0.15s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = '#6C63FF';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = 'rgba(255, 255, 255, 0.5)';
          }}
        >
          <Clipboard size={18} />
        </button>
      </div>

      {showValidation && !valid && (
        <motion.p
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          style={{
            color: '#FF6584',
            fontSize: '13px',
            margin: 0,
            paddingLeft: '4px',
          }}
        >
          {t('urlInvalid')}
        </motion.p>
      )}

      <motion.button
        whileHover={valid && !isSubmitting ? { scale: 1.02 } : undefined}
        whileTap={valid && !isSubmitting ? { scale: 0.98 } : undefined}
        onClick={handleSubmit}
        disabled={!valid || isSubmitting}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '10px',
          padding: '14px 28px',
          background:
            valid && !isSubmitting
              ? 'linear-gradient(135deg, #6C63FF, #8B7DFF)'
              : 'rgba(108, 99, 255, 0.3)',
          border: 'none',
          borderRadius: '14px',
          color: valid && !isSubmitting ? '#fff' : 'rgba(255, 255, 255, 0.5)',
          fontSize: '15px',
          fontWeight: 600,
          fontFamily: 'inherit',
          cursor: valid && !isSubmitting ? 'pointer' : 'not-allowed',
          transition: 'all 0.2s ease',
        }}
      >
        {t('btnProcess')}
        <ArrowRight size={18} />
      </motion.button>
    </div>
  );
}
