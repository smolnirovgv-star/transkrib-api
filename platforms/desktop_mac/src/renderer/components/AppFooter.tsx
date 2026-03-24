import React from 'react';
import { version } from '../../../package.json';
import { Film, Scissors } from 'lucide-react';
import { useTranslation } from '../i18n';

interface Props {
  onNavigate?:    (screen: number) => void;
  onShowGallery?: () => void;
  onShowPrivacy?: () => void;
  onShowDocs?:    () => void;
  onOpenGuide?:   () => void;
  resultCount?:   number;
}

export const AppFooter: React.FC<Props> = ({ onNavigate, onShowGallery, onShowPrivacy, onShowDocs, onOpenGuide, resultCount = 0 }) => {
  const { t } = useTranslation();

  const handleTelegram = () => {
    const url = 'https://t.me/video_transkrib';
    if (window.electronAPI && (window.electronAPI as any).openExternal) {
      (window.electronAPI as any).openExternal(url);
    } else {
      window.open(url, '_blank');
    }
  };

  const handleTerms = () => {
    const url = 'https://trans-smarttv.tilda.ws/terms';
    if (window.electronAPI && (window.electronAPI as any).openExternal) {
      (window.electronAPI as any).openExternal(url);
    } else {
      window.open(url, '_blank');
    }
  };

  return (
    <footer className="app-footer-v2">
      <div className="app-footer-main">
        <div className="app-footer-brand">
          <div className="app-footer-logo">
            <div className="app-logo-icon-wrap app-logo-icon-sm">
              <Scissors size={13} className="app-logo-scissors" />
            </div>
            <span className="app-logo-bold">Transkrib</span>
            <span className="app-logo-thin">SmartCut AI</span>
          </div>
          <p className="app-footer-desc">{t('footer.description')}</p>
          <p className="app-footer-year">© 2026</p>
        </div>

        <div className="app-footer-links-col">
          <button className="app-footer-nav-link" onClick={() => onNavigate?.(0)}>{t('nav.main')}</button>
          <button className="app-footer-nav-link" onClick={() => onNavigate?.(1)}>{t('nav.howItWorks')}</button>
          <button className="app-footer-nav-link" onClick={() => onNavigate?.(2)}>{t('nav.pricing')}</button>
          <button
            className={'app-footer-results-link' + (resultCount > 0 ? ' active' : '')}
            onClick={resultCount > 0 ? onShowGallery : undefined}
            disabled={resultCount === 0}
          >
            <Film size={13} />
            {t('nav.myVideos')}{resultCount > 0 ? ` (${resultCount})` : ''}
          </button>
          <button className="app-footer-nav-link" onClick={onOpenGuide ?? onShowDocs}>{t('footer.docs')}</button>
        </div>

        <div className="app-footer-right-col">
          <p className="app-footer-made">{t('footer.madeWith')}</p>
          <div className="footer-socials">
            <button className="footer-social-btn" title="Telegram" onClick={handleTelegram}>TG</button>
            <button className="footer-social-btn" title="YouTube">YT</button>
            <button className="footer-social-btn" title="VK">VK</button>
          </div>
        </div>
      </div>

      <div className="app-footer-bottom">
        <span className="footer-copy">{t('footer.copyright')}</span>
        <div className="footer-bottom-links">
          <button className="footer-link" onClick={onShowPrivacy}>{t('footer.privacy')}</button>
          <span className="footer-sep">·</span>
          <button className="footer-link" onClick={handleTerms}>{t('footer.terms')}</button>
        </div>
        <span className="footer-version">v{version}</span>
      </div>
    </footer>
  );
};
