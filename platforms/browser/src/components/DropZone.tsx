import React, { useState, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Upload, Loader2 } from 'lucide-react';
import { useTranslation } from '../i18n';

interface DropZoneProps {
  onFileSelected: (file: File) => void;
  isUploading: boolean;
}

export function DropZone({ onFileSelected, isUploading }: DropZoneProps) {
  const { t } = useTranslation();
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);

      const files = e.dataTransfer.files;
      if (files.length > 0 && !isUploading) {
        onFileSelected(files[0]);
      }
    },
    [onFileSelected, isUploading]
  );

  const handleClick = useCallback(() => {
    if (!isUploading) {
      fileInputRef.current?.click();
    }
  }, [isUploading]);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        onFileSelected(files[0]);
      }
      // Reset input so the same file can be selected again
      e.target.value = '';
    },
    [onFileSelected]
  );

  const borderColor = isUploading
    ? 'rgba(108, 99, 255, 0.4)'
    : isDragOver
      ? '#6C63FF'
      : 'rgba(108, 99, 255, 0.3)';

  const borderStyle = isDragOver || isUploading ? 'solid' : 'dashed';

  return (
    <motion.div
      whileHover={!isUploading ? { scale: 1.02 } : undefined}
      whileTap={!isUploading ? { scale: 0.98 } : undefined}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={handleClick}
      style={{
        position: 'relative',
        padding: '48px 24px',
        border: `2px ${borderStyle} ${borderColor}`,
        borderRadius: '20px',
        textAlign: 'center',
        cursor: isUploading ? 'wait' : 'pointer',
        background: isDragOver
          ? 'rgba(108, 99, 255, 0.08)'
          : 'rgba(255, 255, 255, 0.02)',
        transition: 'all 0.25s ease',
        boxShadow: isDragOver
          ? '0 0 30px rgba(108, 99, 255, 0.2), inset 0 0 30px rgba(108, 99, 255, 0.05)'
          : 'none',
      }}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept="video/*,audio/*"
        onChange={handleFileChange}
        style={{ display: 'none' }}
      />

      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '16px',
        }}
      >
        {isUploading ? (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
          >
            <Loader2 size={48} color="#6C63FF" />
          </motion.div>
        ) : (
          <motion.div
            animate={isDragOver ? { y: -4 } : { y: 0 }}
            transition={{ type: 'spring', stiffness: 300 }}
          >
            <Upload
              size={48}
              color={isDragOver ? '#6C63FF' : 'rgba(108, 99, 255, 0.6)'}
              strokeWidth={1.5}
            />
          </motion.div>
        )}

        <p
          style={{
            color: isDragOver ? '#fff' : 'rgba(255, 255, 255, 0.6)',
            fontSize: '15px',
            fontWeight: 400,
            margin: 0,
            lineHeight: 1.5,
            maxWidth: '320px',
            transition: 'color 0.2s ease',
          }}
        >
          {isUploading
            ? t('uploadProgress') + '...'
            : isDragOver
              ? t('dropZoneActive')
              : t('dropZone')}
        </p>
      </div>
    </motion.div>
  );
}
