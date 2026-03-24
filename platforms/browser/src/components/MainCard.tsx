import { useState } from 'react';
import { motion } from 'framer-motion';
import { useTranslation } from '../i18n';
import { DropZone } from './DropZone';
import { UrlInput } from './UrlInput';

interface MainCardProps {
  onFileSelected: (file: File) => void;
  onUrlSubmit: (url: string) => void;
  isUploading: boolean;
  isSubmitting: boolean;
}

export function MainCard({ onFileSelected, onUrlSubmit, isUploading, isSubmitting }: MainCardProps) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<'file' | 'link'>('file');

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: 0.2 }}
      style={{
        maxWidth: '580px',
        width: '100%',
        margin: '0 auto',
        padding: '0 16px',
      }}
    >
      <div
        style={{
          background: 'rgba(255, 255, 255, 0.06)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '24px',
          padding: '32px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.05)',
        }}
      >
        {/* Tab Switcher */}
        <div
          style={{
            display: 'flex',
            background: 'rgba(255, 255, 255, 0.05)',
            borderRadius: '12px',
            padding: '4px',
            marginBottom: '28px',
          }}
        >
          {(['file', 'link'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                flex: 1,
                padding: '10px 0',
                border: 'none',
                borderRadius: '10px',
                background:
                  activeTab === tab
                    ? 'linear-gradient(135deg, rgba(108, 99, 255, 0.4), rgba(108, 99, 255, 0.2))'
                    : 'transparent',
                color:
                  activeTab === tab
                    ? '#fff'
                    : 'rgba(255, 255, 255, 0.5)',
                fontSize: '14px',
                fontWeight: activeTab === tab ? 600 : 400,
                fontFamily: 'inherit',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                position: 'relative',
              }}
            >
              {tab === 'file' ? t('tabFile') : t('tabLink')}
              {activeTab === tab && (
                <motion.div
                  layoutId="activeTab"
                  style={{
                    position: 'absolute',
                    bottom: '-1px',
                    left: '30%',
                    right: '30%',
                    height: '2px',
                    background: '#6C63FF',
                    borderRadius: '1px',
                  }}
                  transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                />
              )}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {activeTab === 'file' ? (
          <DropZone onFileSelected={onFileSelected} isUploading={isUploading} />
        ) : (
          <UrlInput onSubmit={onUrlSubmit} isSubmitting={isSubmitting} />
        )}
      </div>
    </motion.div>
  );
}
