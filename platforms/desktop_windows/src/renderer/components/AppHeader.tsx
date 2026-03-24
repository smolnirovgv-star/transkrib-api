import React, { useState, useRef, useEffect } from 'react';
import { Film, LogOut, Scissors, Settings } from 'lucide-react';
import { useTranslation } from '../i18n';

interface AuthUser { id: string; email?: string; }

interface Props {
  currentScreen: number;
  onNavigate:    (i: number) => void;
  onSettings:    () => void;
  onShowGallery: () => void;
  resultCount:   number;
  user?:         AuthUser | null;
  onLogin?:      () => void;
  onRegister?:   () => void;
  onSignOut?:    () => void;
  onChangePassword?: () => void;
}

const TOTAL_SCREENS = 3;

export const AppHeader: React.FC<Props> = ({
  currentScreen, onNavigate, onSettings, onShowGallery, resultCount,
  user, onLogin, onRegister, onSignOut, onChangePassword,
}) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const handler = (e: MouseEvent) => { if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);
  const { t } = useTranslation();
  const initial = user?.email ? user.email[0].toUpperCase() : '';

  const NAV_ITEMS = [
    { label: t('nav.main'),       screen: 0 },
    { label: t('nav.howItWorks'), screen: 1 },
    { label: t('nav.pricing'),    screen: 2 },
  ];

  return (
    <header className="app-header app-header-glass">
      <div className="app-header-logo">
        <div className="app-logo-icon-wrap">
          <Scissors size={16} className="app-logo-scissors" />
        </div>
        <span className="app-logo-bold">Transkrib</span>
        <span className="app-logo-thin">SmartCut AI</span>
      </div>

      <nav className="app-header-nav">
        {NAV_ITEMS.map(item => (
          <button key={item.screen}
            className={'app-nav-link' + (currentScreen === item.screen ? ' active' : '')}
            onClick={() => onNavigate(item.screen)}>
            {item.label}
          </button>
        ))}
        <button className="app-nav-link app-nav-link-muted" disabled>
          {t('nav.history')}
        </button>
        <button
          className={"app-nav-link" + (resultCount > 0 ? " app-nav-link-gallery" : " app-nav-link-muted")}
          onClick={resultCount > 0 ? onShowGallery : undefined}
          disabled={resultCount === 0}
        >
          <Film size={13} style={{marginRight:4,verticalAlign:'middle'}} />
          {t('nav.myVideos')}{resultCount > 0 ? ` (${resultCount})` : ''}
        </button>
      </nav>

      <div className="app-header-right">
        <button
          className={"app-header-results-btn" + (resultCount === 0 ? " disabled" : "")}
          onClick={resultCount > 0 ? onShowGallery : undefined}
          disabled={resultCount === 0}
          title={resultCount > 0 ? `Готовые видео (${resultCount})` : "Нет готовых видео"}
        >
          <Film size={14} />
          <span>{resultCount > 0 ? resultCount : ""}</span>
        </button>
        <button className="app-header-settings-btn" onClick={onSettings} title="Настройки">
          <Settings size={15} />
        </button>
        {user ? (
          <div className="app-header-user" ref={menuRef} style={{position:'relative'}}>
            <button className="app-header-user-btn" onClick={() => setMenuOpen(v => !v)}
              style={{display:'flex',alignItems:'center',gap:6,background:'none',border:'none',cursor:'pointer',padding:'4px 8px',borderRadius:8}}>
              <div className="app-header-user-avatar" title={user.email}>{initial}</div>
              <span className="app-header-user-email">{user.email?.split('@')[0]}</span>
              <span style={{fontSize:10,opacity:0.6}}>▾</span>
            </button>
            {menuOpen && (
              <div style={{position:'absolute',top:'calc(100% + 6px)',right:0,background:'var(--card-bg,#1e1e2e)',border:'1px solid var(--border-color,rgba(255,255,255,0.1))',borderRadius:10,padding:'4px 0',minWidth:180,zIndex:500,boxShadow:'0 8px 24px rgba(0,0,0,0.4)'}}>
                <button onClick={() => { setMenuOpen(false); onChangePassword?.(); }}
                  style={{width:'100%',textAlign:'left',padding:'8px 16px',background:'none',border:'none',cursor:'pointer',fontSize:13,color:'var(--text-primary,#fff)',display:'flex',alignItems:'center',gap:8}}>
                  🔑 {t('auth.changePassword')}
                </button>
                <button style={{width:'100%',textAlign:'left',padding:'8px 16px',background:'none',border:'none',cursor:'pointer',fontSize:13,color:'var(--text-secondary,#94a3b8)',display:'flex',alignItems:'center',gap:8}} disabled>
                  🪪 {t('auth.myLicense')}
                </button>
                <div style={{height:1,background:'var(--border-color,rgba(255,255,255,0.08))',margin:'4px 0'}} />
                <button onClick={() => { setMenuOpen(false); onSignOut?.(); }}
                  style={{width:'100%',textAlign:'left',padding:'8px 16px',background:'none',border:'none',cursor:'pointer',fontSize:13,color:'#ef4444',display:'flex',alignItems:'center',gap:8}}>
                  <LogOut size={13} /> {t('auth.signOut') || 'Выйти'}
                </button>
              </div>
            )}
          </div>
        ) : (
          <>
            <button className="app-nav-btn-ghost" onClick={onLogin}>{t('header.login')}</button>
            <button className="app-nav-btn-primary" onClick={onRegister}>{t('header.start')} →</button>
          </>
        )}
      </div>
    </header>
  );
};
