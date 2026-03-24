import { motion } from 'framer-motion';
import { useTranslation } from '../i18n';

export function Hero() {
  const { t } = useTranslation();

  return (
    <motion.section
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8, ease: 'easeOut' }}
      style={{
        textAlign: 'center',
        padding: '48px 16px 32px',
      }}
    >
      <h1
        style={{
          fontSize: 'clamp(2.5rem, 6vw, 4.5rem)',
          fontWeight: 800,
          lineHeight: 1.1,
          marginBottom: '16px',
          background: 'linear-gradient(135deg, #6C63FF 0%, #FF6584 50%, #6C63FF 100%)',
          backgroundSize: '200% 200%',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          animation: 'gradientShift 4s ease infinite',
        }}
      >
        {t('appName')}
      </h1>
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4, duration: 0.6 }}
        style={{
          fontSize: 'clamp(1rem, 2.5vw, 1.35rem)',
          color: 'rgba(255, 255, 255, 0.7)',
          fontWeight: 300,
          maxWidth: '540px',
          margin: '0 auto',
          letterSpacing: '0.02em',
        }}
      >
        {t('slogan')}
      </motion.p>

      <style>{`
        @keyframes gradientShift {
          0% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
          100% { background-position: 0% 50%; }
        }
      `}</style>
    </motion.section>
  );
}
