import { motion } from 'framer-motion';
import { Download, Play } from 'lucide-react';
import { useTranslation } from '../i18n';
import { api } from '../services/api';

interface ResultsSectionProps {
  resultFilename: string;
}

export function ResultsSection({ resultFilename }: ResultsSectionProps) {
  const { t } = useTranslation();

  const streamUrl = api.getStreamUrl(resultFilename);
  const downloadUrl = api.getDownloadUrl(resultFilename);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
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
          padding: '28px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.2)',
        }}
      >
        {/* Title */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            marginBottom: '20px',
          }}
        >
          <Play size={20} color="#6C63FF" />
          <h3
            style={{
              margin: 0,
              fontSize: '18px',
              fontWeight: 600,
              color: '#fff',
            }}
          >
            {t('resultTitle')}
          </h3>
        </div>

        {/* Video Player */}
        <div
          style={{
            borderRadius: '14px',
            overflow: 'hidden',
            background: '#000',
            marginBottom: '20px',
            border: '1px solid rgba(255, 255, 255, 0.08)',
          }}
        >
          <video
            controls
            preload="metadata"
            style={{
              width: '100%',
              display: 'block',
              maxHeight: '360px',
            }}
          >
            <source src={streamUrl} />
          </video>
        </div>

        {/* File Info */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
            flexWrap: 'wrap',
          }}
        >
          <div
            style={{
              fontSize: '13px',
              color: 'rgba(255, 255, 255, 0.5)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              maxWidth: '320px',
            }}
          >
            {resultFilename}
          </div>

          {/* Download Button */}
          <motion.a
            href={downloadUrl}
            download
            whileHover={{ scale: 1.04 }}
            whileTap={{ scale: 0.96 }}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 20px',
              background: 'linear-gradient(135deg, #6C63FF, #8B7DFF)',
              border: 'none',
              borderRadius: '12px',
              color: '#fff',
              fontSize: '14px',
              fontWeight: 600,
              fontFamily: 'inherit',
              cursor: 'pointer',
              textDecoration: 'none',
              transition: 'box-shadow 0.2s ease',
              boxShadow: '0 4px 14px rgba(108, 99, 255, 0.3)',
            }}
          >
            <Download size={16} />
            {t('btnDownload')}
          </motion.a>
        </div>
      </div>
    </motion.div>
  );
}
