import { useState } from 'react';
import { Shield, Database, Rocket, CheckCircle, XCircle } from 'lucide-react';
import { useTranslation } from '../i18n';
import { TitleBar } from './TitleBar';

interface TrialStatus {
  state: 'new' | 'active' | 'warning' | 'expired' | 'blocked';
  remaining_days: number;
  today_count: number;
  daily_limit: number;
}

interface SetupWizardProps {
  onComplete: () => void;
  onTrialStart: () => void;
  trialStatus: TrialStatus | null;
}

export function SetupWizard({ onComplete, onTrialStart, trialStatus }: SetupWizardProps) {
  const { t } = useTranslation();
  const [currentStep, setCurrentStep] = useState(1);
  const [licenseKey, setLicenseKey] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [whisperProgress, setWhisperProgress] = useState(0);
  const [privacyAccepted, setPrivacyAccepted] = useState(false);

  const totalSteps = 3;
  const trialExpired = trialStatus?.state === 'expired' || trialStatus?.state === 'blocked';

  const handleLicenseActivation = async () => {
    if (!licenseKey.trim()) { setError('Введите лицензионный ключ'); return; }
    setIsProcessing(true);
    setError('');
    try {
      const result = await window.electronAPI.activateLicense(licenseKey.trim());
      if (result.success) {
        setSuccess('Лицензия успешно активирована!');
        setTimeout(() => { setCurrentStep(2); setError(''); setSuccess(''); startWhisperDownload(); }, 1000);
      } else {
        setError(result.error || 'Не удалось активировать лицензию');
      }
    } catch (err) { setError(`Ошибка: ${err}`); }
    finally { setIsProcessing(false); }
  };

  const startWhisperDownload = async () => {
    setWhisperProgress(0);
    try {
      const status = await window.electronAPI.checkWhisperModel();
      if (status.downloaded) {
        setWhisperProgress(100);
        setSuccess('Модель Whisper уже загружена!');
        setTimeout(() => setCurrentStep(3), 1000);
        return;
      }
      await window.electronAPI.prepareWhisper();
      const checkInterval = setInterval(async () => {
        const s = await window.electronAPI.checkWhisperModel();
        if (s.downloaded) {
          clearInterval(checkInterval);
          setWhisperProgress(100);
          setSuccess('Загрузка завершена!');
          setTimeout(() => setCurrentStep(3), 1000);
        } else {
          setWhisperProgress((prev) => Math.min(prev + 10, 90));
        }
      }, 2000);
    } catch (err) {
      setError(`Ошибка загрузки модели: ${err}`);
    }
  };

  return (
    <div className="app-shell">
      <TitleBar />
      <div className="wizard-overlay">
      <div className="wizard-card glass-card">
        <div className="wizard-header">
          <h1>Добро пожаловать в Transkrib</h1>
          <span className="wizard-step-label">Шаг {currentStep} из {totalSteps}</span>
        </div>

        <div className="wizard-dots">
          {[1, 2, 3].map((s) => (
            <div key={s} className={`wizard-dot ${s === currentStep ? 'active' : s < currentStep ? 'completed' : ''}`} />
          ))}
        </div>

        {currentStep === 1 && (
          <div className="wizard-step">
            <div className="wizard-icon"><Shield size={48} /></div>
            <h2>Активация лицензии</h2>
            <p className="wizard-desc">Введите лицензионный ключ для активации Transkrib</p>

            <label>Лицензионный ключ</label>
            <input
              className="url-input"
              placeholder="TRSK-BASE-XXXX-XXXX-XXXX"
              value={licenseKey}
              onChange={(e) => setLicenseKey(e.target.value)}
              disabled={isProcessing}
              onKeyDown={(e) => { if (e.key === 'Enter') handleLicenseActivation(); }}
            />
            <small style={{ color: '#888' }}>Формат: TRSK-BASE/STND/PREM-XXXX-XXXX-XXXX</small>

            {error && <div className="wizard-error"><XCircle size={16} /> {error}</div>}
            {success && <div className="wizard-success"><CheckCircle size={16} /> {success}</div>}

            <div style={{display:'flex',alignItems:'flex-start',gap:8,margin:'12px 0 4px',cursor:'pointer'}}
              onClick={() => setPrivacyAccepted(p => !p)}>
              <input type="checkbox" checked={privacyAccepted} readOnly
                style={{marginTop:3,cursor:'pointer',accentColor:'#6366f1',flexShrink:0}} />
              <span style={{fontSize:12,color:'#999',userSelect:'none',lineHeight:1.5}}>
                Принимаю <span style={{color:'#6366f1'}}>Политику конфиденциальности</span> и <span style={{color:'#6366f1'}}>Лицензионное соглашение</span>
              </span>
            </div>

            <div className="wizard-actions">
              <button className="btn-primary" onClick={handleLicenseActivation}
                disabled={isProcessing || !licenseKey.trim()}>
                {isProcessing ? 'Активация...' : 'Активировать'}
              </button>
            </div>

            <div className="wizard-trial-divider"><span>или</span></div>

            {trialExpired ? (
              <div className="wizard-error" style={{ justifyContent: 'center' }}>
                <XCircle size={16} /> {t('trial.expired')}
              </div>
            ) : (
              <div className="wizard-trial-section">
                <button className="wizard-trial-btn" onClick={onTrialStart}
                  disabled={!privacyAccepted} style={{opacity:privacyAccepted?1:0.45,cursor:privacyAccepted?"pointer":"not-allowed"}}>
                  {t('trial.startButton')}
                </button>
                <p className="wizard-trial-hint">{t('trial.startHint')}</p>
              </div>
            )}

            {import.meta.env.DEV && (
              <div style={{ marginTop: 20, textAlign: 'center' }}>
                <button
                  style={{ fontSize: 11, padding: '4px 12px', opacity: 0.6, background: 'transparent',
                    border: '1px dashed #666', borderRadius: 4, color: '#aaa', cursor: 'pointer' }}
                  onClick={onComplete}
                >
                  DEV: Пропустить setup
                </button>
              </div>
            )}
          </div>
        )}

        {currentStep === 2 && (
          <div className="wizard-step">
            <div className="wizard-icon"><Database size={48} /></div>
            <h2>Модель Whisper</h2>
            <p className="wizard-desc">Загрузка модели OpenAI Whisper для транскрипции<br />Одноразовая загрузка (~461 МБ)</p>

            <div className="wizard-progress-bar">
              <div className="wizard-progress-fill" style={{ width: `${whisperProgress}%` }} />
            </div>
            <p style={{ textAlign: 'center' }}>{whisperProgress}% завершено</p>

            {error && <div className="wizard-error"><XCircle size={16} /> {error}</div>}
            {success && <div className="wizard-success"><CheckCircle size={16} /> {success}</div>}

            <div className="wizard-actions">
              <button className="btn-secondary" onClick={() => setCurrentStep(3)}>
                Пропустить (загрузить позже)
              </button>
            </div>
          </div>
        )}

        {currentStep === 3 && (
          <div className="wizard-step">
            <div className="wizard-icon"><Rocket size={48} /></div>
            <h2>Готово к работе!</h2>
            <p className="wizard-desc">Настройка завершена. Можно начать транскрипцию видео.</p>

            <div className="wizard-actions">
              <button className="btn-primary btn-large" onClick={onComplete}>
                Начать работу с Transkrib
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
    </div>
  );
}
