import React, { useState, useCallback } from 'react';
import { Link, Check, AlertCircle } from 'lucide-react';
import { useTranslation } from '../i18n';
import { ContextMenu } from './ContextMenu';

interface Props {
  onSubmit: (url: string) => void;
}

export const UrlInput: React.FC<Props> = ({ onSubmit }) => {
  const { t } = useTranslation();
  const [url, setUrl] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null);
  const isValid = /^https?:\/\/.+/.test(url.trim());

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setMenu({ x: e.clientX, y: e.clientY });
  }, []);

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      setUrl(text);
    } catch {}
  };

  const menuItems = [
    { label: 'Вставить ссылку', onClick: handlePaste },
    { label: 'Очистить поле', onClick: () => setUrl(''), disabled: !url },
    { label: 'Отправить на обработку', onClick: () => { if (!submitting) { setSubmitting(true); onSubmit(url.trim()); } }, disabled: !isValid || submitting },
  ];

  return (
    <div className="url-input-container">
      <div className="url-input-wrapper">
        <Link size={16} className="url-icon-left" />
        <input
          type="text"
          className="url-input"
          placeholder={t('urlInput.placeholder')}
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && isValid && !submitting) { setSubmitting(true); onSubmit(url.trim()); } }}
          onContextMenu={handleContextMenu}
        />
        {url && (
          <span className="url-icon-right">
            {isValid
              ? <Check size={15} className="validation-ok" />
              : <AlertCircle size={15} className="validation-err" />
            }
          </span>
        )}
      </div>
      <button
        className="btn-primary"
        disabled={!isValid || submitting}
        onClick={() => { if (!submitting) { setSubmitting(true); onSubmit(url.trim()); } }}
      >
        {t('urlInput.submit')}
      </button>
      {menu && (
        <ContextMenu
          x={menu.x}
          y={menu.y}
          items={menuItems}
          onClose={() => setMenu(null)}
        />
      )}
    </div>
  );
};
