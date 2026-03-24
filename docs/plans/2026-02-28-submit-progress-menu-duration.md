# Submit Fix + Progress Bar + Context Menu + Video Duration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix submit button error visibility, add inline progress bar for URL processing, add right-click context menu on URL input, add video length selector in settings, remove API key from SetupWizard, and wire max_duration through backend pipeline.

**Architecture:** Frontend changes span 6 files + 2 new components. Backend changes in pipeline.py, standalone_tasks.py, standalone_tasks_router.py, and standalone_server.py (universal_runner). All changes are additive — existing trial/license gates remain untouched.

**Tech Stack:** React + TypeScript, FastAPI + Python, WebSocket progress, threading.Thread backend tasks.

---

### Task 1: Backend — Add max_duration_seconds through pipeline

**Files:**
- Modify: `app/backend/app/pipeline.py` (run_pipeline and run_url_pipeline)
- Modify: `app/backend/app/workers/standalone_tasks.py` (run_video_task and run_url_task)

**Context:** `pipeline.py` currently hardcodes `settings.target_highlight_max_seconds` in the `analyze_highlights()` call. We add an optional `max_duration_seconds` param that overrides it when provided.

**Step 1: Edit pipeline.py — run_pipeline signature and analyze call**

In `run_pipeline`, change signature from:
```python
def run_pipeline(
    task_id: str, video_path: Path, original_name: str,
    ffmpeg, transcriber, analyzer, storage, progress,
):
```
To:
```python
def run_pipeline(
    task_id: str, video_path: Path, original_name: str,
    ffmpeg, transcriber, analyzer, storage, progress,
    max_duration_seconds: int | None = None,
):
```

Change the `analyze_highlights` call from:
```python
fragments = analyzer.analyze_highlights(
    transcript, duration,
    settings.target_highlight_ratio_min,
    settings.target_highlight_ratio_max,
    settings.target_highlight_max_seconds,
)
```
To:
```python
_max_dur = max_duration_seconds if max_duration_seconds else settings.target_highlight_max_seconds
fragments = analyzer.analyze_highlights(
    transcript, duration,
    settings.target_highlight_ratio_min,
    settings.target_highlight_ratio_max,
    _max_dur,
)
```

**Step 2: Edit pipeline.py — run_url_pipeline signature and call**

In `run_url_pipeline`, change signature to add `max_duration_seconds: int | None = None` as last param. Inside, after calling `run_pipeline(...)`, pass it through:

Find the inner `run_pipeline(...)` call in `run_url_pipeline` and add `max_duration_seconds=max_duration_seconds`.

**Step 3: Edit standalone_tasks.py — run_video_task**

Change signature from `run_video_task(task_id: str, file_path: str, original_name: str)` to:
```python
def run_video_task(task_id: str, file_path: str, original_name: str, max_duration_seconds: int | None = None):
```

Pass it to `run_pipeline(...)`:
```python
run_pipeline(
    task_id, Path(file_path), original_name,
    ffmpeg, transcriber, analyzer, storage, progress,
    max_duration_seconds=max_duration_seconds,
)
```

**Step 4: Edit standalone_tasks.py — run_url_task**

Change signature from `run_url_task(task_id: str, url: str)` to:
```python
def run_url_task(task_id: str, url: str, max_duration_seconds: int | None = None):
```

Pass it to `run_url_pipeline(...)`:
```python
run_url_pipeline(
    task_id, url, ffmpeg, transcriber, analyzer, storage, progress,
    max_duration_seconds=max_duration_seconds,
)
```

---

### Task 2: Backend — Router and universal_runner accept max_duration_seconds

**Files:**
- Modify: `app/backend/app/routers/standalone_tasks_router.py`
- Modify: `app/backend/standalone_server.py` (universal_runner function)

**Step 1: Edit standalone_tasks_router.py — UrlSubmission model**

Change:
```python
class UrlSubmission(BaseModel):
    url: str
```
To:
```python
class UrlSubmission(BaseModel):
    url: str
    max_duration_seconds: int | None = None
```

**Step 2: Edit standalone_tasks_router.py — upload_video endpoint**

Add `max_duration_seconds: int | None = Form(None)` parameter to upload_video:
```python
async def upload_video(
    file: UploadFile = File(...),
    max_duration_seconds: int | None = Form(None),
):
```

Change thread args from:
```python
thread = threading.Thread(
    target=_pipeline_runner,
    args=(task_id, str(file_path), file.filename),
    daemon=True,
)
```
To:
```python
thread = threading.Thread(
    target=_pipeline_runner,
    args=(task_id, str(file_path), file.filename, max_duration_seconds),
    daemon=True,
)
```

**Step 3: Edit standalone_tasks_router.py — submit_url endpoint**

Change thread args from:
```python
thread = threading.Thread(
    target=_pipeline_runner,
    args=(task_id, url),
    daemon=True,
)
```
To:
```python
thread = threading.Thread(
    target=_pipeline_runner,
    args=(task_id, url, None, submission.max_duration_seconds),
    daemon=True,
)
```

**Step 4: Edit standalone_server.py — universal_runner**

Change from:
```python
def universal_runner(task_id: str, path_or_url: str, original_name: str = None):
    if original_name:
        run_video_task(task_id, path_or_url, original_name)
    else:
        run_url_task(task_id, path_or_url)
```
To:
```python
def universal_runner(task_id: str, path_or_url: str, original_name: str = None, max_duration_seconds: int = None):
    if original_name:
        run_video_task(task_id, path_or_url, original_name, max_duration_seconds=max_duration_seconds)
    else:
        run_url_task(task_id, path_or_url, max_duration_seconds=max_duration_seconds)
```

---

### Task 3: Frontend — api.ts supports max_duration_seconds

**Files:**
- Modify: `app/platforms/desktop_windows/src/renderer/services/api.ts`

**Step 1: Update submitUrl**

Change from:
```typescript
async submitUrl(url: string): Promise<TaskResponse> {
    const res = await fetch(`${getBaseUrl()}/api/tasks/url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
```
To:
```typescript
async submitUrl(url: string, maxDurationSeconds?: number): Promise<TaskResponse> {
    const res = await fetch(`${getBaseUrl()}/api/tasks/url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, max_duration_seconds: maxDurationSeconds ?? null }),
    });
```

**Step 2: Update uploadFile**

Change from:
```typescript
async uploadFile(file: File): Promise<TaskResponse> {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${getBaseUrl()}/api/tasks/upload`, { method: 'POST', body: form });
```
To:
```typescript
async uploadFile(file: File, maxDurationSeconds?: number): Promise<TaskResponse> {
    const form = new FormData();
    form.append('file', file);
    if (maxDurationSeconds) form.append('max_duration_seconds', String(maxDurationSeconds));
    const res = await fetch(`${getBaseUrl()}/api/tasks/upload`, { method: 'POST', body: form });
```

---

### Task 4: Frontend — SettingsPanel video length selector

**Files:**
- Modify: `app/platforms/desktop_windows/src/renderer/components/SettingsPanel.tsx`

**Context:** Add duration selector buttons below language selector. Options: 5 / 10 / 15 / 20 / 30 / ∞ (minutes). Default 15. Saved in `localStorage('transkrib-video-duration')`.

**Step 1: Rewrite SettingsPanel.tsx**

```tsx
import React, { useState } from 'react';
import { Settings, Globe, Clock } from 'lucide-react';
import { useTranslation, Language } from '../i18n';

interface Props {
  open: boolean;
  onClose: () => void;
}

const DURATION_OPTIONS = [
  { label: '5 мин', value: 5 * 60 },
  { label: '10 мин', value: 10 * 60 },
  { label: '15 мин', value: 15 * 60 },
  { label: '20 мин', value: 20 * 60 },
  { label: '30 мин', value: 30 * 60 },
  { label: '∞', value: 0 },
];

export const DURATION_STORAGE_KEY = 'transkrib-video-duration';
export const DEFAULT_DURATION = 15 * 60; // 900s

export function getSelectedDuration(): number {
  const saved = localStorage.getItem(DURATION_STORAGE_KEY);
  if (saved !== null) return parseInt(saved, 10);
  return DEFAULT_DURATION;
}

export const SettingsPanel: React.FC<Props> = ({ open, onClose }) => {
  const { t, language, setLanguage } = useTranslation();
  const [duration, setDuration] = useState<number>(getSelectedDuration);

  const handleDuration = (val: number) => {
    setDuration(val);
    localStorage.setItem(DURATION_STORAGE_KEY, String(val));
  };

  if (!open) return null;

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-panel glass-card" onClick={(e) => e.stopPropagation()}>
        <h3><Settings size={18} /> {t('settings.title')}</h3>

        <label><Globe size={14} /> {t('settings.language')}</label>
        <div className="lang-buttons">
          {(['ru', 'en', 'zh'] as Language[]).map((l) => (
            <button key={l} className={`btn-lang ${language === l ? 'active' : ''}`}
              onClick={() => setLanguage(l)}>
              {l.toUpperCase()}
            </button>
          ))}
        </div>

        <label style={{ marginTop: '16px' }}><Clock size={14} /> {t('settings.videoDuration')}</label>
        <div className="duration-buttons">
          {DURATION_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              className={`btn-duration ${duration === opt.value ? 'active' : ''}`}
              onClick={() => handleDuration(opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <div className="settings-actions">
          <button className="btn-primary" onClick={onClose}>{t('settings.save')}</button>
        </div>
      </div>
    </div>
  );
};
```

**Step 2: Add i18n key `settings.videoDuration` to all 3 translation files**

In `ru.ts` settings block add: `videoDuration: 'Длина итогового видео',`
In `en.ts` settings block add: `videoDuration: 'Output video length',`
In `zh.ts` settings block add: `videoDuration: '输出视频长度',`

**Step 3: Add CSS for duration buttons in globals.css**

Append at end of `globals.css`:
```css
/* ============ Duration selector ============ */

.duration-buttons {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.btn-duration {
  padding: 5px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-strong);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 500;
  font-family: var(--font-family);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-duration:hover {
  border-color: var(--color-primary);
  color: var(--color-text);
}

.btn-duration.active {
  background: var(--color-primary);
  color: #FFFFFF;
  border-color: var(--color-primary);
}
```

---

### Task 5: Frontend — App.tsx passes duration + shows submit error

**Files:**
- Modify: `app/platforms/desktop_windows/src/renderer/App.tsx`

**Context:** Import `getSelectedDuration` from SettingsPanel. Pass maxDuration to api calls. Add `submitError` state and show it in UI. Track `sourceTab` to know if URL or file triggered processing.

**Step 1: Add imports and new state**

At top of App.tsx, add import:
```tsx
import { getSelectedDuration } from './components/SettingsPanel';
```

Add new state variables after existing ones:
```tsx
const [submitError, setSubmitError] = useState<string | null>(null);
const [sourceTab, setSourceTab] = useState<Tab>('file');
```

**Step 2: Update handleFile**

```tsx
const handleFile = async (file: File) => {
  setSubmitError(null);
  try {
    const maxDur = getSelectedDuration() || undefined;
    const res = await api.uploadFile(file, maxDur);
    setTaskId(res.task_id);
    setSourceTab('file');
    setPhase('processing');
  } catch (e: any) {
    setSubmitError(e.message || 'Ошибка при загрузке файла');
  }
};
```

**Step 3: Update handleUrl**

```tsx
const handleUrl = async (url: string) => {
  setSubmitError(null);
  try {
    const maxDur = getSelectedDuration() || undefined;
    const res = await api.submitUrl(url, maxDur);
    setTaskId(res.task_id);
    setSourceTab('url');
    setPhase('processing');
  } catch (e: any) {
    setSubmitError(e.message || 'Ошибка при отправке ссылки');
  }
};
```

**Step 4: Update handleBack to clear submitError**

```tsx
const handleBack = () => {
  setPhase('input');
  setTaskId(null);
  setSubmitError(null);
};
```

**Step 5: Add error display in input-section JSX**

After the DropZone/UrlInput block (but inside `{phase === 'input' && ...}`), add:
```tsx
{submitError && (
  <div className="submit-error">
    {submitError}
  </div>
)}
```

**Step 6: Pass sourceTab to processing phase**

In the processing phase JSX, pass `sourceTab` to StepCards or the new ProcessingProgress component (Task 6 handles this).

---

### Task 6: Frontend — ProcessingProgress component

**Files:**
- Create: `app/platforms/desktop_windows/src/renderer/components/ProcessingProgress.tsx`

**Context:** Linear horizontal progress bar showing 4 stages with icons. Used when `phase === 'processing'` and `sourceTab === 'url'`. Stages map from WebSocket state: `downloading/converting` → stage 0, `transcribing` → stage 1, `analyzing` → stage 2, `assembling` → stage 3.

**Step 1: Create ProcessingProgress.tsx**

```tsx
import React from 'react';
import { Download, Mic, Brain, Film, Check } from 'lucide-react';

interface Props {
  state: string | null;
  progress: number;
  submittedUrl?: string;
}

const STAGES = [
  { key: 'downloading', label: 'Скачивание', icon: Download, states: ['downloading', 'converting'] },
  { key: 'transcribing', label: 'Транскрибация', icon: Mic, states: ['transcribing'] },
  { key: 'analyzing', label: 'Анализ', icon: Brain, states: ['analyzing'] },
  { key: 'assembling', label: 'Сборка видео', icon: Film, states: ['assembling'] },
];

function getActiveStage(state: string | null): number {
  if (!state) return -1;
  for (let i = 0; i < STAGES.length; i++) {
    if (STAGES[i].states.includes(state)) return i;
  }
  if (state === 'completed') return STAGES.length;
  return -1;
}

export const ProcessingProgress: React.FC<Props> = ({ state, progress, submittedUrl }) => {
  const activeIdx = getActiveStage(state);

  return (
    <div className="proc-progress">
      {submittedUrl && (
        <div className="proc-url-display">
          <span className="proc-url-text">{submittedUrl}</span>
        </div>
      )}
      <div className="proc-stages">
        {STAGES.map((stage, idx) => {
          const done = idx < activeIdx;
          const active = idx === activeIdx;
          const Icon = stage.icon;
          return (
            <React.Fragment key={stage.key}>
              <div className={`proc-stage ${done ? 'done' : active ? 'active' : 'pending'}`}>
                <div className="proc-stage-icon">
                  {done ? <Check size={16} /> : <Icon size={16} />}
                </div>
                <span className="proc-stage-label">{stage.label}</span>
                {active && <span className="proc-stage-pct">{Math.round(progress)}%</span>}
              </div>
              {idx < STAGES.length - 1 && (
                <div className={`proc-connector ${done ? 'done' : ''}`} />
              )}
            </React.Fragment>
          );
        })}
      </div>
      <div className="proc-bar-track">
        <div
          className="proc-bar-fill"
          style={{ width: `${Math.min(100, (activeIdx / (STAGES.length - 1)) * 100 + (progress / (STAGES.length - 1)))}%` }}
        />
      </div>
    </div>
  );
};
```

**Step 2: Integrate into App.tsx processing phase**

In App.tsx, add import:
```tsx
import { ProcessingProgress } from './components/ProcessingProgress';
```

Change the processing phase block to show ProcessingProgress for URL source, StepCards for file source:
```tsx
{phase === 'processing' && (
  <div className="progress-section">
    {sourceTab === 'url' ? (
      <ProcessingProgress state={state} progress={progress} submittedUrl={taskId ? undefined : undefined} />
    ) : (
      <>
        <h2 className="section-title">{t('steps.processing')}</h2>
        <StepCards currentState={state} progress={progress} />
      </>
    )}
  </div>
)}
```

Note: `submittedUrl` — we need to store the submitted URL. Add state `const [submittedUrl, setSubmittedUrl] = useState('')` and set it in `handleUrl` before calling `api.submitUrl`.

**Step 3: Add CSS for ProcessingProgress in globals.css**

Append:
```css
/* ============ Processing Progress (URL mode) ============ */

.proc-progress {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 24px;
  max-width: 560px;
  margin: 0 auto;
  width: 100%;
}

.proc-url-display {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 10px 14px;
  overflow: hidden;
}

.proc-url-text {
  font-size: 12px;
  color: var(--color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
}

.proc-stages {
  display: flex;
  align-items: center;
  gap: 0;
}

.proc-stage {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.proc-stage-icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--color-border-strong);
  background: var(--color-surface);
  color: var(--color-text-tertiary);
  transition: all var(--transition-normal);
}

.proc-stage.done .proc-stage-icon {
  background: var(--color-success);
  border-color: var(--color-success);
  color: #FFFFFF;
}

.proc-stage.active .proc-stage-icon {
  border-color: var(--color-primary);
  color: var(--color-primary);
  box-shadow: 0 0 0 4px var(--color-primary-glow);
  animation: proc-pulse 1.5s ease-in-out infinite;
}

@keyframes proc-pulse {
  0%, 100% { box-shadow: 0 0 0 4px var(--color-primary-glow); }
  50% { box-shadow: 0 0 0 8px rgba(108,99,255,0.1); }
}

.proc-stage-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text-tertiary);
  text-align: center;
  white-space: nowrap;
}

.proc-stage.done .proc-stage-label,
.proc-stage.active .proc-stage-label {
  color: var(--color-text);
}

.proc-stage-pct {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-primary);
}

.proc-connector {
  flex: 1;
  height: 2px;
  background: var(--color-border-strong);
  margin: 0 4px;
  margin-bottom: 24px;
  transition: background var(--transition-normal);
}

.proc-connector.done {
  background: var(--color-success);
}

.proc-bar-track {
  width: 100%;
  height: 4px;
  background: var(--color-border);
  border-radius: 2px;
  overflow: hidden;
}

.proc-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-primary), var(--color-accent));
  border-radius: 2px;
  transition: width 0.4s ease;
}

/* Submit error */
.submit-error {
  margin-top: 12px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: var(--color-error);
  font-size: 13px;
  max-width: 560px;
  width: 100%;
}
```

---

### Task 7: Frontend — ContextMenu component for URL input

**Files:**
- Create: `app/platforms/desktop_windows/src/renderer/components/ContextMenu.tsx`
- Modify: `app/platforms/desktop_windows/src/renderer/components/UrlInput.tsx`

**Step 1: Create ContextMenu.tsx**

```tsx
import React, { useEffect, useRef } from 'react';

export interface ContextMenuItem {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}

interface Props {
  x: number;
  y: number;
  items: ContextMenuItem[];
  onClose: () => void;
}

export const ContextMenu: React.FC<Props> = ({ x, y, items, onClose }) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [onClose]);

  return (
    <div
      ref={ref}
      className="context-menu"
      style={{ position: 'fixed', top: y, left: x, zIndex: 99999 }}
    >
      {items.map((item, i) => (
        <button
          key={i}
          className={`context-menu-item${item.disabled ? ' disabled' : ''}`}
          onClick={() => { if (!item.disabled) { item.onClick(); onClose(); } }}
          disabled={item.disabled}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
};
```

**Step 2: Update UrlInput.tsx to use ContextMenu**

Rewrite UrlInput.tsx:
```tsx
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
    { label: 'Отправить на обработку', onClick: () => onSubmit(url.trim()), disabled: !isValid },
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
          onKeyDown={(e) => e.key === 'Enter' && isValid && onSubmit(url.trim())}
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
        disabled={!isValid}
        onClick={() => onSubmit(url.trim())}
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
```

**Step 3: Add CSS for ContextMenu in globals.css**

Append:
```css
/* ============ Context Menu ============ */

.context-menu {
  background: var(--color-surface-solid);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-xl);
  padding: 4px;
  min-width: 180px;
  overflow: hidden;
}

.context-menu-item {
  display: block;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: transparent;
  color: var(--color-text);
  font-size: 13px;
  font-family: var(--font-family);
  text-align: left;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: background var(--transition-fast);
}

.context-menu-item:hover:not(:disabled) {
  background: var(--color-primary-light);
}

.context-menu-item.disabled,
.context-menu-item:disabled {
  color: var(--color-text-tertiary);
  cursor: default;
}
```

---

### Task 8: Frontend — Remove API Key step from SetupWizard

**Files:**
- Modify: `app/platforms/desktop_windows/src/renderer/components/SetupWizard.tsx`

**Context:** SetupWizard has 4 steps: 1=License, 2=API Key, 3=Whisper, 4=Done. Remove Step 2 entirely. After license activation → go directly to step 2 (Whisper). Renumber: totalSteps=3, step 1=License, step 2=Whisper, step 3=Done.

**Step 1: Rewrite SetupWizard.tsx**

```tsx
import { useState } from 'react';
import { Shield, Database, Rocket, CheckCircle, XCircle } from 'lucide-react';
import { useTranslation } from '../i18n';

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

  const totalSteps = 3;
  const trialExpired = trialStatus?.state === 'expired' || trialStatus?.state === 'blocked';

  const handleLicenseActivation = async () => {
    if (!licenseKey.trim()) { setError('Please enter a license key'); return; }
    setIsProcessing(true);
    setError('');
    try {
      const result = await window.electronAPI.activateLicense(licenseKey.trim());
      if (result.success) {
        setSuccess('License activated successfully!');
        setTimeout(() => { setCurrentStep(2); setError(''); setSuccess(''); startWhisperDownload(); }, 1000);
      } else {
        setError(result.error || 'Failed to activate license');
      }
    } catch (err) { setError(`Error: ${err}`); }
    finally { setIsProcessing(false); }
  };

  const startWhisperDownload = async () => {
    setWhisperProgress(0);
    try {
      const status = await window.electronAPI.checkWhisperModel();
      if (status.downloaded) {
        setWhisperProgress(100);
        setSuccess('Whisper model already downloaded!');
        setTimeout(() => setCurrentStep(3), 1000);
        return;
      }
      await window.electronAPI.prepareWhisper();
      const checkInterval = setInterval(async () => {
        const s = await window.electronAPI.checkWhisperModel();
        if (s.downloaded) {
          clearInterval(checkInterval);
          setWhisperProgress(100);
          setSuccess('Download complete!');
          setTimeout(() => setCurrentStep(3), 1000);
        } else {
          setWhisperProgress((prev) => Math.min(prev + 10, 90));
        }
      }, 2000);
    } catch (err) {
      setError(`Failed to download Whisper model: ${err}`);
    }
  };

  return (
    <div className="wizard-overlay">
      <div className="wizard-card glass-card">
        <div className="wizard-header">
          <h1>Welcome to Transkrib</h1>
          <span className="wizard-step-label">Step {currentStep} of {totalSteps}</span>
        </div>

        <div className="wizard-dots">
          {[1, 2, 3].map((s) => (
            <div key={s} className={`wizard-dot ${s === currentStep ? 'active' : s < currentStep ? 'completed' : ''}`} />
          ))}
        </div>

        {currentStep === 1 && (
          <div className="wizard-step">
            <div className="wizard-icon"><Shield size={48} /></div>
            <h2>License Activation</h2>
            <p className="wizard-desc">Enter your license key to activate Transkrib</p>

            <label>License Key</label>
            <input
              className="url-input"
              placeholder="TRSK-BASE-XXXX-XXXX-XXXX"
              value={licenseKey}
              onChange={(e) => setLicenseKey(e.target.value)}
              disabled={isProcessing}
              onKeyDown={(e) => { if (e.key === 'Enter') handleLicenseActivation(); }}
            />
            <small style={{ color: '#888' }}>Format: TRSK-BASE/STND/PREM-XXXX-XXXX-XXXX</small>

            {error && <div className="wizard-error"><XCircle size={16} /> {error}</div>}
            {success && <div className="wizard-success"><CheckCircle size={16} /> {success}</div>}

            <div className="wizard-actions">
              <button className="btn-primary" onClick={handleLicenseActivation} disabled={isProcessing || !licenseKey.trim()}>
                {isProcessing ? 'Activating...' : 'Activate'}
              </button>
            </div>

            <div className="wizard-trial-divider"><span>или</span></div>

            {trialExpired ? (
              <div className="wizard-error" style={{ justifyContent: 'center' }}>
                <XCircle size={16} /> {t('trial.expired')}
              </div>
            ) : (
              <div className="wizard-trial-section">
                <button className="wizard-trial-btn" onClick={onTrialStart}>
                  {t('trial.startButton')}
                </button>
                <p className="wizard-trial-hint">{t('trial.startHint')}</p>
              </div>
            )}
          </div>
        )}

        {currentStep === 2 && (
          <div className="wizard-step">
            <div className="wizard-icon"><Database size={48} /></div>
            <h2>Whisper Model</h2>
            <p className="wizard-desc">Downloading OpenAI Whisper model for transcription<br />This is a one-time download (~461MB)</p>

            <div className="wizard-progress-bar">
              <div className="wizard-progress-fill" style={{ width: `${whisperProgress}%` }} />
            </div>
            <p style={{ textAlign: 'center' }}>{whisperProgress}% complete</p>

            {error && <div className="wizard-error"><XCircle size={16} /> {error}</div>}
            {success && <div className="wizard-success"><CheckCircle size={16} /> {success}</div>}

            <div className="wizard-actions">
              <button className="btn-secondary" onClick={() => setCurrentStep(3)}>
                Skip (download later)
              </button>
            </div>
          </div>
        )}

        {currentStep === 3 && (
          <div className="wizard-step">
            <div className="wizard-icon"><Rocket size={48} /></div>
            <h2>Ready to Go!</h2>
            <p className="wizard-desc">Setup complete. You can now start transcribing videos.</p>

            <div className="wizard-actions">
              <button className="btn-primary btn-large" onClick={onComplete}>
                Start Using Transkrib
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

---

### Task 9: Rebuild installer

**What:** Run `rebuild_installer.bat` manually after all code changes.

**Step 1:** Run `C:\Users\Admin\OneDrive\Desktop\Cursor\app\rebuild_installer.bat`

Expected result: `release/Transkrib-Setup-1.0.0.exe` + arch-specific variants.
