import React, { useState } from 'react';
import { X, Mail, Lock, Eye, EyeOff, ArrowLeft } from 'lucide-react';
import { supabase, supabaseConfigured } from '../lib/supabaseClient';
import { useTranslation } from '../i18n';

type View = 'login' | 'register' | 'forgot' | 'reset';

interface Props {
  initialView?: View;
  linkExpired?: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export const AuthModal: React.FC<Props> = ({ initialView = 'login', linkExpired, onClose, onSuccess }) => {
  const { t } = useTranslation();
  const [view, setView]               = useState<View>(linkExpired && initialView === 'reset' ? 'forgot' : initialView);
  const [email, setEmail]             = useState('');
  const [password, setPassword]       = useState('');
  const [confirm, setConfirm]         = useState('');
  const [showPass, setShowPass]       = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showNewPass, setShowNewPass] = useState(false);
  const [showConfirmPass, setShowConfirmPass] = useState(false);
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState<string | null>(linkExpired ? 'Ссылка для сброса пароля устарела или уже использована. Введите email, чтобы получить новую.' : null);
  const [message, setMessage]         = useState<string | null>(null);

  const reset = () => { setError(null); setMessage(null); };
  const go = (v: View) => { setView(v); reset(); };

  if (!supabaseConfigured) {
    return (
      <div className="auth-overlay" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
        <div className="auth-card glass-card">
          <div className="auth-header">
            <h2 className="auth-title">{t('auth.loginTitle')}</h2>
            <button className="auth-close btn-icon" onClick={onClose}><X size={16} /></button>
          </div>
          <p style={{ padding: '16px', color: '#94a3b8', textAlign: 'center' }}>{t('auth.notConfigured')}</p>
        </div>
      </div>
    );
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault(); reset(); setLoading(true);
    try {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;
      onSuccess?.(); onClose();
    } catch (err: any) {
      setError(err.message === 'Invalid login credentials'
        ? t('auth.errorInvalidCreds')
        : err.message === 'Email not confirmed'
        ? 'Email not confirmed'
        : err.message || t('auth.loginError'));
    } finally { setLoading(false); }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault(); reset();
    if (password !== confirm) { setError(t('auth.errorPasswordMismatch')); return; }
    if (password.length < 6) { setError(t('auth.errorPasswordShort')); return; }
    setLoading(true);
    try {
      const { error } = await supabase.auth.signUp({ email, password });
      if (error) throw error;
      setMessage(t('auth.successConfirmSent').replace('{email}', email));
    } catch (err: any) {
      setError(err.message === 'User already registered'
        ? t('auth.errorAlreadyRegistered')
        : err.message || t('auth.registerError'));
    } finally { setLoading(false); }
  };

  const handleForgot = async (e: React.FormEvent) => {
    e.preventDefault(); reset(); setLoading(true);
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: 'https://transkrib.su/parol-smena',
      });
      if (error) throw error;
      setMessage(t('auth.successResetSent').replace('{email}', email));
    } catch (err: any) {
      setError(err.message || t('auth.loginError'));
    } finally { setLoading(false); }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault(); reset();
    if (newPassword !== confirmPassword) { setError(t('auth.errorPasswordMismatch')); return; }
    if (newPassword.length < 6) { setError(t('auth.errorPasswordShort')); return; }
    setLoading(true);
    try {
      const { error } = await supabase.auth.updateUser({ password: newPassword });
      if (error) throw error;
      setMessage(t('auth.passwordChanged'));
      window.history.replaceState({}, '', window.location.pathname);
      setTimeout(() => go('login'), 2000);
    } catch (err: any) {
      setError(err.message || 'Ошибка смены пароля');
    } finally { setLoading(false); }
  };

  return (
    <div className="auth-overlay" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="auth-card glass-card">
        <div className="auth-header">
          {view !== 'login' && (
            <button className="auth-back btn-icon" onClick={() => go('login')}>
              <ArrowLeft size={16} />
            </button>
          )}
          <h2 className="auth-title">
            {view === 'login'    && t('auth.loginTitle')}
            {view === 'register' && t('auth.registerTitle')}
            {view === 'forgot'   && t('auth.forgotTitle')}
            {view === 'reset'    && t('auth.resetTitle')}
          </h2>
          <button className="auth-close btn-icon" onClick={onClose}><X size={16} /></button>
        </div>
        {view !== 'forgot' && view !== 'reset' && (
          <div className="auth-tabs">
            <button type="button" className={'auth-tab' + (view === 'login' ? ' active' : '')} onClick={() => go('login')}>
              {t('auth.tabLogin')}
            </button>
            <button type="button" className={'auth-tab' + (view === 'register' ? ' active' : '')} onClick={() => go('register')}>
              {t('auth.tabRegister')}
            </button>
          </div>
        )}
        {error   && <div className="auth-alert auth-alert-error">{error}</div>}
        {message && <div className="auth-alert auth-alert-success">{message}</div>}
        {view === 'login' && !message && (
          <form className="auth-form" onSubmit={handleLogin}>
            <div className="auth-field">
              <Mail size={15} className="auth-field-icon" />
              <input className="auth-input" type="email" placeholder={t('auth.email')}
                value={email} onChange={e => setEmail(e.target.value)} required autoFocus />
            </div>
            <div className="auth-field">
              <Lock size={15} className="auth-field-icon" />
              <input className="auth-input" type={showPass ? 'text' : 'password'}
                placeholder={t('auth.password')}
                value={password} onChange={e => setPassword(e.target.value)} required />
              <button type="button" className="auth-eye" onClick={() => setShowPass(v => !v)}>
                {showPass ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
            <button className="btn-primary" type="submit" disabled={loading}
              style={{ width: '100%', justifyContent: 'center', marginTop: 4 }}>
              {loading ? t('auth.loginLoading') : t('auth.loginBtn')}
            </button>
            <button type="button" className="auth-link" onClick={() => go('forgot')}>
              {t('auth.forgotLink')}
            </button>
          </form>
        )}
        {view === 'register' && !message && (
          <form className="auth-form" onSubmit={handleRegister}>
            <div className="auth-field">
              <Mail size={15} className="auth-field-icon" />
              <input className="auth-input" type="email" placeholder={t('auth.email')}
                value={email} onChange={e => setEmail(e.target.value)} required autoFocus />
            </div>
            <div className="auth-field">
              <Lock size={15} className="auth-field-icon" />
              <input className="auth-input" type={showPass ? 'text' : 'password'}
                placeholder={t('auth.passwordHint')}
                value={password} onChange={e => setPassword(e.target.value)} required />
              <button type="button" className="auth-eye" onClick={() => setShowPass(v => !v)}>
                {showPass ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
            <div className="auth-field">
              <Lock size={15} className="auth-field-icon" />
              <input className="auth-input" type={showConfirm ? 'text' : 'password'}
                placeholder={t('auth.confirmPassword')}
                value={confirm} onChange={e => setConfirm(e.target.value)} required />
              <button type="button" className="auth-eye" onClick={() => setShowConfirm(v => !v)}>
                {showConfirm ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
            <button className="btn-primary" type="submit" disabled={loading}
              style={{ width: '100%', justifyContent: 'center', marginTop: 4 }}>
              {loading ? t('auth.registerLoading') : t('auth.registerBtn')}
            </button>
          </form>
        )}
        {view === 'forgot' && !message && (
          <form className="auth-form" onSubmit={handleForgot}>
            <p className="auth-desc">{t('auth.forgotDesc')}</p>
            <div className="auth-field">
              <Mail size={15} className="auth-field-icon" />
              <input className="auth-input" type="email" placeholder={t('auth.email')}
                value={email} onChange={e => setEmail(e.target.value)} required autoFocus />
            </div>
            <button className="btn-primary" type="submit" disabled={loading}
              style={{ width: '100%', justifyContent: 'center', marginTop: 4 }}>
              {loading ? t('auth.forgotLoading') : t('auth.forgotBtn')}
            </button>
          </form>
        )}
        {view === 'reset' && !message && (
          <form className="auth-form" onSubmit={handleResetPassword}>
            <div className="auth-field">
              <Lock size={15} className="auth-field-icon" />
              <input className="auth-input" type={showNewPass ? 'text' : 'password'}
                placeholder={t('auth.newPassword')}
                value={newPassword} onChange={e => setNewPassword(e.target.value)} required autoFocus />
              <button type="button" className="auth-eye" onClick={() => setShowNewPass(v => !v)}>
                {showNewPass ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
            <div className="auth-field">
              <Lock size={15} className="auth-field-icon" />
              <input className="auth-input" type={showConfirmPass ? 'text' : 'password'}
                placeholder={t('auth.confirmNewPassword')}
                value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} required />
              <button type="button" className="auth-eye" onClick={() => setShowConfirmPass(v => !v)}>
                {showConfirmPass ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
            <button className="btn-primary" type="submit" disabled={loading}
              style={{ width: '100%', justifyContent: 'center', marginTop: 4 }}>
              {loading ? '...' : t('auth.savePassword')}
            </button>
          </form>
        )}
        <div className="auth-divider">
          <span>{t('auth.divider')}</span>
        </div>
        <button className="auth-skip" onClick={onClose}>
          {t('auth.skip')}
        </button>
      </div>
    </div>
  );
};
