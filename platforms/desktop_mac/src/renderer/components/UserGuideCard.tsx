import React, { useState } from 'react';
import { X } from 'lucide-react';
import { useTranslation } from '../i18n';

interface Props {
  onOpen: () => void;
}

const SEEN_KEY = 'transkrib_guide_seen';

export const UserGuideCard: React.FC<Props> = ({ onOpen }) => {
  const { t } = useTranslation();
  const [dismissed, setDismissed] = useState(() =>
    localStorage.getItem(SEEN_KEY) === 'true'
  );

  if (dismissed) return null;

  const handleDismiss = () => {
    localStorage.setItem(SEEN_KEY, 'true');
    setDismissed(true);
  };

  const handleOpen = () => {
    localStorage.setItem(SEEN_KEY, 'true');
    setDismissed(true);
    onOpen();
  };

  return (
    <div className="guide-card">
      <button className="guide-card-close btn-icon" onClick={handleDismiss} type="button">
        <X size={14} />
      </button>
      <p className="guide-card-title">📖 {t('guide.cardTitle')}</p>
      <p className="guide-card-text">{t('guide.cardText')}</p>
      <button className="guide-card-btn" onClick={handleOpen} type="button">
        {t('guide.cardBtn')}
      </button>
    </div>
  );
};
