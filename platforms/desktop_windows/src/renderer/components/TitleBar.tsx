import React from 'react';
import { Minus, Square, X, Sun, Moon } from 'lucide-react';
import { useTranslation } from '../i18n';
import type { Language } from '../i18n';
import { useTheme } from '../theme';

const LANG_LABELS: Record<Language, string> = {
  ru: 'РУ',
  en: 'EN',
  zh: '中',
};

const LANGUAGES: Language[] = ['ru', 'en', 'zh'];

export const TitleBar: React.FC = () => {
  const { t, language, setLanguage } = useTranslation();
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="title-bar">
      <div className="title-bar-drag">
        <svg width="28" height="28" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" style={{marginRight:8,flexShrink:0}}><path d="M24 2 L44 10 L44 26 C44 36 34 44 24 46 C14 44 4 36 4 26 L4 10 Z" fill="#7C3AED" stroke="#5B21B6" strokeWidth="1.5"/><rect x="14" y="14" width="20" height="3" rx="1.5" fill="white"/><rect x="21.5" y="17" width="5" height="16" rx="2" fill="white"/></svg>
        <span className="title-bar-text">{t('titleBar.appName')}</span>
      </div>

      <div className="title-bar-actions">
        <div className="titlebar-lang-group">
          {LANGUAGES.map((lang) => (
            <button
              key={lang}
              className={`titlebar-lang-btn${language === lang ? ' active' : ''}`}
              onClick={() => setLanguage(lang)}
              title={t(`languages.${lang}` as any)}
            >
              {LANG_LABELS[lang]}
            </button>
          ))}
        </div>

        <button
          className="titlebar-theme-btn"
          onClick={toggleTheme}
          title={theme === 'light' ? t('settings.themeDark') : t('settings.themeLight')}
        >
          {theme === 'light' ? <Moon size={13} /> : <Sun size={13} />}
        </button>
      </div>

      <div className="title-bar-controls">
        <button className="title-btn" onClick={() => (window as any).electronAPI?.windowMinimize?.()}>
          <Minus size={12} />
        </button>
        <button className="title-btn" onClick={() => (window as any).electronAPI?.windowMaximize?.()}>
          <Square size={12} />
        </button>
        <button className="title-btn title-btn-close" onClick={() => (window as any).electronAPI?.windowClose?.()}>
          <X size={12} />
        </button>
      </div>
    </div>
  );
};
