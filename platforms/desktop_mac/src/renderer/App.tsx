import React, { useState, useEffect, useRef } from 'react';
import { ArrowLeft } from 'lucide-react';
import { useTranslation } from './i18n';
import { TitleBar } from './components/TitleBar';
import { DropZone } from './components/DropZone';
import { UrlInput } from './components/UrlInput';
import { StepCards } from './components/StepCards';
import { ResultGallery } from './components/ResultGallery';
import { SettingsPanel, getSelectedDuration, getSelectedModel } from './components/SettingsPanel';
import { SetupWizard } from './components/SetupWizard';
import { BackendStartup } from './components/BackendStartup';
import { ProcessingProgress } from './components/ProcessingProgress';
import { DemoModal } from './components/DemoModal';
import { HowItWorks } from './components/HowItWorks';
import { AppHeader } from './components/AppHeader';
import { AppFooter } from './components/AppFooter';
import { Pricing } from './components/Pricing';
import { AuthModal } from './components/AuthModal';
import { PrivacyPolicy } from './components/PrivacyPolicy';
import { DocsPage } from './components/DocsPage';
import { DocViewer } from './components/DocViewer';
import type { DocId } from './components/DocsPage';
import { useAuth } from './hooks/useAuth';
import { useTaskProgress } from './hooks/useTaskProgress';
import { supabase, supabaseConfigured } from './lib/supabaseClient';
import { api } from './services/api';
import { UserGuideCard } from './components/UserGuideCard';
import { GuideModal } from './components/GuideModal';
import { TaskBriefModal } from './components/TaskBriefModal';
import type { UserBrief } from './components/TaskBriefModal';
import { OnboardingScreen, useOnboarding } from './components/OnboardingScreen';

type Tab   = 'file' | 'url';
type Phase = 'input' | 'processing' | 'result' | 'gallery';

interface TrialStatus {
  state: 'new' | 'active' | 'warning' | 'expired' | 'blocked';
  remaining_days: number;
  today_count: number;
  daily_limit: number;
  warning?: boolean;
}

const TRIAL_STARTED_KEY = 'transkrib-trial-started';
const SCREEN_COUNT = 3;

const isDev = import.meta.env.DEV && (
  new URLSearchParams(window.location.search).get('dev') === 'true' ||
  (() => { try { return localStorage.getItem('transkrib_dev_mode') === 'true'; } catch { return false; } })()
);

const App: React.FC = () => {
  const { t } = useTranslation();
  const [backendReady, setBackendReady]   = useState(false);
  const [tab, setTab]                     = useState<Tab>('file');
  const [settingsOpen, setSettingsOpen]   = useState(false);
  const [taskId, setTaskId]               = useState<string | null>(null);
  const [phase, setPhase]                 = useState<Phase>('input');
  const [resultCount, setResultCount]     = useState(0);
  const [isLicensed, setIsLicensed]       = useState<boolean | null>(null);
  const [trialStatus, setTrialStatus]     = useState<TrialStatus | null>(null);
  const [trialStarted, setTrialStarted]   = useState(
    () => localStorage.getItem(TRIAL_STARTED_KEY) === 'true'
  );
  const [showDemo, setShowDemo]           = useState(false);
  const [showAuth, setShowAuth]           = useState(false);
  const [showPrivacy, setShowPrivacy]       = useState(false);
  const [showDocs, setShowDocs]             = useState(false);
  const [showGuide, setShowGuide]           = useState(false);
  const [showBrief, setShowBrief]           = useState(false);
  const [pendingSubmit, setPendingSubmit]   = useState<(() => Promise<void>) | null>(null);
  const [userBrief, setUserBrief]           = useState<UserBrief | null>(null);
  const [currentDoc, setCurrentDoc]         = useState<DocId | null>(null);
  const [showPasswordReset, setShowPasswordReset] = useState(false);
  const [passwordResetExpired, setPasswordResetExpired] = useState(false);
  const [resetFromEmail, setResetFromEmail]             = useState(false);
  const [authView, setAuthView]           = useState<'login' | 'register'>('login');
  const [screen, setScreen]               = useState(0);
  const [submitError, setSubmitError]     = useState<string | null>(null);
  const [isUploading, setIsUploading]     = useState(false);
  const [uploadFileName, setUploadFileName] = useState('');
  const [sourceTab, setSourceTab]         = useState<Tab>('file');
  const [submittedUrl, setSubmittedUrl]   = useState('');
  const [resultFilename, setResultFilename] = useState<string | null>(null);

  const uploadRef = useRef<HTMLDivElement>(null);
  const { state, progress, error } = useTaskProgress(taskId);
  const { user, signOut } = useAuth();
  const { show: showOnboarding, close: closeOnboarding } = useOnboarding();

  useEffect(() => {
    if (!(window as any).electronAPI) return;
    const cleanup = (window as any).electronAPI.onDeepLink((url: string) => {
      if (url.includes('reset-password')) {
        setShowPasswordReset(true);
      }
    });
    return cleanup;
  }, []);

  useEffect(() => {
    const hash   = window.location.hash;
    const search = window.location.search;
    const isRecovery = hash.includes('type=recovery') || search.includes('type=recovery');
    if (isRecovery) {
      // Parse tokens from hash (valid link) or detect error (expired link)
      const hashParams   = new URLSearchParams(hash.slice(1));
      const accessToken  = hashParams.get('access_token');
      const refreshToken = hashParams.get('refresh_token');
      const hashError    = hashParams.get('error');
      window.history.replaceState({}, '', window.location.pathname);
      // Set both flags synchronously so early return fires on same render tick
      setResetFromEmail(true);
      setShowPasswordReset(true);
      if (hashError) setPasswordResetExpired(true);
      // For valid link: establish session in background (form already shown)
      if (supabaseConfigured && accessToken && refreshToken) {
        supabase.auth.setSession({ access_token: accessToken, refresh_token: refreshToken });
      }
    } else if (hash.includes('type=signup') || hash.includes('type=magiclink')) {
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);

  useEffect(() => {
    if (!backendReady) return;
    const init = async () => {
      try {
        const backendUrl = await window.electronAPI.getBackendUrl();
        if (backendUrl) localStorage.setItem('transkrib-backend-url', backendUrl);
      } catch {}
      try {
        const [licResult, trialResult] = await Promise.all([
          window.electronAPI.checkLicense().catch(() => ({ licensed: false })),
          window.electronAPI.checkTrial().catch(() => ({
            state: 'new' as const, remaining_days: 7, today_count: 0, daily_limit: 3,
          })),
        ]);
        setIsLicensed(licResult.licensed);
        setTrialStatus(trialResult);
      } catch {
        setIsLicensed(false);
        setTrialStatus({ state: 'new', remaining_days: 7, today_count: 0, daily_limit: 3 });
      }
    };
    init();
  }, [backendReady]);

  useEffect(() => {
    if (state === 'completed' || state === 'failed') setPhase('result');
  }, [state]);

  // Browser mode polling (electronAPI unavailable)
  useEffect(() => {
    if (phase !== 'processing' || !taskId || (window as any).electronAPI) return;
    let cancelled = false;
    const poll = async () => {
      if (cancelled) return;
      try {
        const r = await fetch('http://127.0.0.1:8000/api/tasks/' + taskId);
        const task = await r.json();
        if (task.state === 'completed' && !cancelled) {
          setPhase('result');
          setTaskId(task.task_id);
          setResultFilename(task.result_filename || null);
        } else if (task.state === 'failed' && !cancelled) {
          setPhase('result');
        } else {
          if (!cancelled) setTimeout(poll, 1000);
        }
      } catch {
        if (!cancelled) setTimeout(poll, 1000);
      }
    };
    poll();
    return () => { cancelled = true; };
  }, [phase, taskId]);

  // Dev mode: restore completed task after F5
  useEffect(() => {
    if (!isDev || window.electronAPI) return;
    console.log('[Dev] Checking for completed tasks...');
    fetch('http://127.0.0.1:8000/api/tasks/')
      .then(r => r.json())
      .then((tasks: any[]) => {
        const completed = tasks.find(t => t.state === 'completed' || t.status === 'completed');
        if (completed) {
          console.log('[Dev] Restoring task:', completed.task_id ?? completed.id, 'file:', completed.result_filename);
          setTaskId(completed.task_id ?? completed.id ?? null);
          setPhase('result');
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!backendReady) return;
    const checkResults = () => {
      if (!window.electronAPI) return;
      window.electronAPI.listResults().then(r => setResultCount(r.length)).catch(() => {});
    };
    checkResults();
    const interval = setInterval(checkResults, 15000);
    return () => clearInterval(interval);
  }, [backendReady]);

  const handleFilePath = async (filePath: string) => {
    setSubmitError(null);
    setUploadFileName(filePath.split(/[\/]/).pop() || filePath);
    const doSubmit = async () => {
      setIsUploading(true);
      try {
        const maxDuration = getSelectedDuration();
        const res = await window.electronAPI.uploadFile(filePath, maxDuration || undefined, getSelectedModel());
        if (res.error) throw new Error(res.error);
        if (!res.task_id) throw new Error('No task_id');
        setTaskId(res.task_id); setSourceTab('file'); setPhase('processing');
      } catch (e: any) { setSubmitError(e?.message || 'Upload failed'); }
      finally { setIsUploading(false); }
    };
    setPendingSubmit(() => doSubmit);
    setShowBrief(true);
  };

  const handleFile = async (file: File) => {
    setSubmitError(null);
    setUploadFileName(file.name);
    const doSubmit = async () => {
      setIsUploading(true);
      try {
        const maxDuration = getSelectedDuration();
        const res = await api.uploadFile(file, maxDuration || undefined, getSelectedModel());
        if (!res.task_id) throw new Error('No task_id');
        setTaskId(res.task_id); setSourceTab('file'); setPhase('processing');
      } catch (e: any) {
        const msg = e?.message || '';
        setSubmitError(msg === 'Failed to fetch' ? 'Бэкенд недоступен. Используйте Electron-приложение.' : (msg || 'Upload failed'));
      }
      finally { setIsUploading(false); }
    };
    setPendingSubmit(() => doSubmit);
    setShowBrief(true);
  };

  const handleUrl = async (url: string) => {
    setSubmitError(null);
    const doSubmit = async () => {
      try {
        const maxDuration = getSelectedDuration();
        let res;
        if (window.electronAPI?.submitUrl) {
          res = await window.electronAPI.submitUrl(url, maxDuration || undefined, getSelectedModel());
          if (res.error) throw new Error(res.error);
        } else {
          res = await api.submitUrl(url, maxDuration || undefined, getSelectedModel());
        }
        if (!res.task_id) throw new Error('No task_id');
        setTaskId(res.task_id); setSourceTab('url'); setSubmittedUrl(url); setPhase('processing');
      } catch (e: any) {
        const msg = e?.message || '';
        setSubmitError(msg === 'Failed to fetch' ? 'Бэкенд недоступен. Запустите Electron-приложение.' : (msg || 'Submit failed'));
      }
    };
    setPendingSubmit(() => doSubmit);
    setShowBrief(true);
  };

  const handleBack     = () => { setPhase('input'); setTaskId(null); setSubmitError(null); };
  const handleShowGallery = () => setPhase('gallery');
  const handleTrialStart = () => {
    localStorage.setItem(TRIAL_STARTED_KEY, 'true');
    setTrialStarted(true);
    // In browser mode (no Electron), mock active trial status so wizard closes
    if (!window.electronAPI) {
      setTrialStatus({ state: 'active', remaining_days: 7, today_count: 0, daily_limit: 3 });
    }
  };
  const goScreen       = (i: number) => setScreen(Math.max(0, Math.min(SCREEN_COUNT - 1, i)));
  const openLogin      = () => { setAuthView('login');    setShowAuth(true); };
  const openRegister   = () => { setAuthView('register'); setShowAuth(true); };

  const scrollToUpload = () => {
    setScreen(0);
    setTimeout(() => uploadRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 420);
  };

  const handlePlanSelect = async (planId: string) => {
    if (planId === 'trial') {
      handleTrialStart();
      setScreen(0);
      return;
    }

    // Если не авторизован - сначала регистрация
    if (!user) {
      openRegister();
      return;
    }

    // Авторизован - создаём платёж через YooKassa
    try {
      const planMap: Record<string, string> = {
        'basic': 'BASE',
        'standard': 'STANDARD',
        'pro': 'PRO'
      };

      const plan = planMap[planId] || planId.toUpperCase();
      const deviceId = localStorage.getItem('device_id') || (() => {
        const id = crypto.randomUUID();
        localStorage.setItem('device_id', id);
        return id;
      })();

      console.log('Sending payment:', { plan, device_id: deviceId, user_email: user?.email });
      const data = await (window as any).electronAPI.createPayment({
        plan,
        device_id: deviceId,
        user_email: user.email
      });
      console.log('Payment data:', data);
      if (data.error) throw new Error(data.error);

      if (data.payment_url) {
        if ((window as any).electronAPI?.openExternal) {
          (window as any).electronAPI.openExternal(data.payment_url);
        } else {
          window.open(data.payment_url, '_blank');
        }
      }
    } catch (err: any) {
      console.error('Payment error:', err);
      const msg = err?.message || JSON.stringify(err) || 'Неизвестная ошибка';
      alert('Ошибка при создании платежа: ' + msg);
    }
  };

  // Email recovery link: bypass backend startup and license checks entirely
  if (resetFromEmail && showPasswordReset) return (
    <div className="app-shell">
      {showOnboarding && (
        <OnboardingScreen onClose={closeOnboarding} />
      )}
      <TitleBar />
      <AuthModal
        initialView={'reset' as any}
        linkExpired={passwordResetExpired}
        onClose={() => { setShowPasswordReset(false); setPasswordResetExpired(false); setResetFromEmail(false); window.history.replaceState({}, '', window.location.pathname); }}
        onSuccess={() => { setShowPasswordReset(false); setPasswordResetExpired(false); setResetFromEmail(false); }}
      />
    </div>
  );

  if (!backendReady) return <BackendStartup onReady={() => setBackendReady(true)} />;

  if (isLicensed === null) return (
    <div className="app-shell">
      <TitleBar />
      <div style={{ display:'flex', alignItems:'center', justifyContent:'center', flex:1, fontSize:16, color:'#888' }}>
        {t('app.loading')}
      </div>
    </div>
  );

  const trialAllowed = trialStarted && trialStatus !== null &&
    (trialStatus.state === 'active' || trialStatus.state === 'warning');

  if (!isLicensed && !trialAllowed && !isDev && !showPasswordReset && !trialStarted) return (
    <SetupWizard
      onComplete={() => setIsLicensed(true)}
      onTrialStart={handleTrialStart}
      trialStatus={trialStatus}
    />
  );



  return (
    <div className="app-shell">
      <TitleBar />

      {phase === 'input' ? (
        <>
          <AppHeader
            currentScreen={screen}
            onNavigate={goScreen}
            onSettings={() => setSettingsOpen(p => !p)}
            onShowGallery={handleShowGallery}
            resultCount={resultCount}
            user={user}
            onLogin={openLogin}
            onRegister={openRegister}
            onSignOut={signOut}
            onChangePassword={() => setShowPasswordReset(true)}
          />

          {!isLicensed && trialAllowed && trialStatus && (
            <div className={`trial-banner${trialStatus.state === 'warning' ? ' trial-banner-warning' : ''}`}>
              <span className="trial-banner-icon">⏱</span>
              <span>
                {t('trial.banner')}: {trialStatus.remaining_days} {t('trial.daysLeft')} · {trialStatus.today_count}/{trialStatus.daily_limit} {t('trial.videosToday')}
              </span>
            </div>
          )}

          {screen === 0 && (
            <div className="screen-main">
              <div className="input-section">
                <div className="screen-1">
                  <div className="hero-section">
                    <h1 className="hero-title">{t('hero.title')}</h1>
                    <p className="hero-subtitle">{t('hero.subtitle')}</p>
                    <div className="hero-actions">
                      <button className="btn-primary btn-large" onClick={scrollToUpload}>
                        {t('hero.tryFree')}
                      </button>
                      <button className="btn-demo" onClick={() => setShowDemo(true)}>
                        {t('hero.watchDemo')}
                      </button>
                    </div>
                    <p className="hero-badges">{t('hero.badges')}</p>
                  </div>

                  <UserGuideCard onOpen={() => setShowGuide(true)} />
                  <div ref={uploadRef} className="upload-area">
                    <div className="tab-bar">
                      <button className={`tab ${tab === 'file' ? 'active' : ''}`} onClick={() => setTab('file')}>
                        {t('tabs.file')}
                      </button>
                      <button className={`tab ${tab === 'url' ? 'active' : ''}`} onClick={() => setTab('url')}>
                        {t('tabs.url')}
                      </button>
                    </div>
                    {tab === 'file' ? (
                      isUploading ? (
                        <div className="upload-loading">
                          <div className="upload-loading-spinner" />
                          <p className="upload-loading-title">{t('hero.uploadLoading')}</p>
                          <p className="upload-loading-name">{uploadFileName}</p>
                        </div>
                      ) : <DropZone onFilePath={handleFilePath} onFile={handleFile} />
                    ) : <UrlInput onSubmit={handleUrl} />}
                    {submitError && <div className="submit-error">{submitError}</div>}
                  </div>
                </div>
              </div>
            </div>
          )}
          {screen === 1 && <div className="screen-how"><HowItWorks /></div>}
          {screen === 2 && <div className="screen-prices"><Pricing onSelect={handlePlanSelect} /></div>}

          <div className="screen-nav-bar">
            <button className="screen-nav-arrow" onClick={() => goScreen(screen - 1)}
              disabled={screen === 0} aria-label="Назад">←</button>
            <div className="screen-nav-dots">
              {Array.from({ length: SCREEN_COUNT }, (_, i) => (
                <button key={i}
                  className={`screen-nav-dot${i === screen ? ' active' : ''}`}
                  onClick={() => goScreen(i)} />
              ))}
            </div>
            <button className="screen-nav-arrow" onClick={() => goScreen(screen + 1)}
              disabled={screen === SCREEN_COUNT - 1} aria-label="Вперёд">→</button>
          </div>

          <AppFooter onNavigate={goScreen} onShowGallery={handleShowGallery} onShowPrivacy={() => setShowPrivacy(true)} onShowDocs={() => setShowDocs(true)} onOpenGuide={() => setShowGuide(true)} resultCount={resultCount} />
        </>
      ) : (
        <div className="app-content">
          {phase === 'processing' && (
            <div className="progress-section">
              <button className="back-btn" onClick={handleBack}>
                <ArrowLeft size={16} />{t('app.back')}
              </button>
              {sourceTab === 'url'
                ? <ProcessingProgress state={state} progress={progress} submittedUrl={submittedUrl} />
                : <><h2 className="section-title">{t('steps.processing')}</h2>
                    <StepCards currentState={state} progress={progress} /></>}
            </div>
          )}
          {phase === 'result' && (
            <>
              <button className="back-btn" onClick={handleBack}>
                <ArrowLeft size={16} />{t('app.back')}
              </button>
              {error
                ? <div className="error-banner glass-card"><span>{t('steps.error')}: {error}</span></div>
                : <div className="completed-banner glass-card">
                    <span className="completed-icon">✓</span>
                    <span>{t('steps.completed')}</span>
                  </div>}
              <ResultGallery onResultCountChange={setResultCount} />
            </>
          )}
          {phase === 'gallery' && (
            <>
              <button className="back-btn" onClick={handleBack}>
                <ArrowLeft size={16} />{t('app.back')}
              </button>
              <ResultGallery onResultCountChange={setResultCount} />
            </>
          )}
        </div>
      )}

      <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      {showDemo && <DemoModal onClose={() => setShowDemo(false)} />}
      {showAuth && (
        <AuthModal
          initialView={authView}
          onClose={() => setShowAuth(false)}
          onSuccess={() => setShowAuth(false)}
        />
      )}
      {showPrivacy && <PrivacyPolicy onClose={() => setShowPrivacy(false)} />}
      {showDocs && !currentDoc && (
        <DocsPage
          onClose={() => setShowDocs(false)}
          onOpenDoc={(id) => setCurrentDoc(id)}
        />
      )}
      {showDocs && currentDoc && (
        <DocViewer
          docId={currentDoc}
          onBack={() => setCurrentDoc(null)}
        />
      )}
      {showGuide && <GuideModal onClose={() => setShowGuide(false)} />}
      {showBrief && (
        <TaskBriefModal
          initialBrief={userBrief ?? undefined}
          onStart={(brief) => {
            setUserBrief(brief);
            setShowBrief(false);
            if (pendingSubmit) { pendingSubmit(); setPendingSubmit(null); }
          }}
          onSkip={() => {
            setShowBrief(false);
            if (pendingSubmit) { pendingSubmit(); setPendingSubmit(null); }
          }}
          onClose={() => { setShowBrief(false); setPendingSubmit(null); }}
        />
      )}
      {showPasswordReset && (
        <AuthModal
          initialView={'reset' as any}
          linkExpired={passwordResetExpired}
          onClose={() => { setShowPasswordReset(false); setPasswordResetExpired(false); }}
          onSuccess={() => { setShowPasswordReset(false); setPasswordResetExpired(false); }}
        />
      )}
    </div>
  );
};

export default App;
