import React, { useState, useCallback } from 'react';
import { Upload, FileVideo } from 'lucide-react';
import { useTranslation } from '../i18n';

interface Props {
  onFilePath: (filePath: string) => void;
  onFile?: (file: File) => void;
}

export const DropZone: React.FC<Props> = ({ onFilePath, onFile }) => {
  const { t } = useTranslation();
  const [isDragging, setIsDragging] = useState(false);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      const nativePath = (file as any).path as string | undefined;
      if (nativePath) onFilePath(nativePath);
      else if (onFile) onFile(file);
    }
  }, [onFilePath, onFile]);

  const handleSelectFile = async () => {
    const ea = (window as any).electronAPI;
    if (ea?.selectFile) {
      const filePath = await ea.selectFile();
      if (filePath) onFilePath(filePath);
    } else {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'video/*';
      input.onchange = () => {
        const file = input.files?.[0];
        if (file) {
          const nativePath = (file as any).path as string | undefined;
          if (nativePath) onFilePath(nativePath);
          else if (onFile) onFile(file);
        }
      };
      input.click();
    }
  };

  return (
    <div
      className={`drop-zone ${isDragging ? 'drag-over' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
    >
      <Upload size={48} className="drop-zone-icon" />
      <p className="drop-zone-text">
        {isDragging ? t('dropZone.dragOver') : t('dropZone.title')}
      </p>
      <button className="btn-primary" onClick={handleSelectFile}>
        <FileVideo size={16} /> {t('dropZone.selectFile')}
      </button>
    </div>
  );
};
