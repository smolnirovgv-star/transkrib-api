import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useTranslation } from '../i18n';
import { api } from '../services/api';

export function Footer() {
  const { t } = useTranslation();
  const [totalProcessed, setTotalProcessed] = useState<number>(0);

  useEffect(() => {
    let mounted = true;

    async function fetchCount() {
      try {
        const results = await api.listResults();
        if (mounted) {
          setTotalProcessed(results.length);
        }
      } catch {
        // Silently ignore -- footer stat is non-critical
      }
    }

    fetchCount();

    // Refresh count every 30 seconds
    const interval = setInterval(fetchCount, 30000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <motion.footer
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6, delay: 0.5 }}
      style={{
        textAlign: 'center',
        padding: '40px 16px 28px',
        marginTop: '48px',
      }}
    >
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          padding: '10px 24px',
          background: 'rgba(255, 255, 255, 0.04)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.06)',
          borderRadius: '50px',
        }}
      >
        <span
          style={{
            fontSize: '13px',
            color: 'rgba(255, 255, 255, 0.4)',
            fontWeight: 400,
          }}
        >
          {t('totalProcessed')}:
        </span>
        <span
          style={{
            fontSize: '14px',
            fontWeight: 700,
            background: 'linear-gradient(135deg, #6C63FF, #FF6584)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
          }}
        >
          {totalProcessed}
        </span>
      </div>
    </motion.footer>
  );
}
