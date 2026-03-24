# Whisper Model Selector + Prompt Improvement + Transcription Animation

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Whisper model selector to settings (БЫСТРО/СРЕДНЯЯ/МЕДЛЕННО), improve Claude prompt to always include speaker greeting/farewell, add sound wave animation during transcription, then rebuild the installer.

**Architecture:** Frontend stores whisper model in localStorage and passes it with every API request (same pattern as `max_duration_seconds`). Backend hot-swaps the `_transcriber` singleton when model changes. Animation is pure CSS bars shown only when `state === 'transcribing'`.

**Tech Stack:** React + TypeScript (frontend), FastAPI + Python (backend), CSS animations, PyInstaller + electron-builder (build)

---

### Task 1: Update Claude API Prompt

**Files:**
- Modify: `app/backend/app/services/analysis_service.py`

**Step 1: Replace HIGHLIGHTS_PROMPT**

In `analysis_service.py`, replace the entire `HIGHLIGHTS_PROMPT` constant (lines 12–28) with:

```python
HIGHLIGHTS_PROMPT = """Ты — профессиональный видеоредактор. Проанализируй транскрипт видео с таймкодами и выбери ключевые смысловые эпизоды.

Общая длительность видео: {duration}
Целевая длительность итогового видео: примерно {target_duration} (10-15% от оригинала, не более 15 минут)

Транскрипт:
{transcript}

Правила выбора фрагментов:
1. Если в начале видео (в первые 2 минуты) спикер приветствует аудиторию или представляется — ОБЯЗАТЕЛЬНО включи этот фрагмент целиком.
2. Если в конце видео (последние 2 минуты) спикер прощается с аудиторией — ОБЯЗАТЕЛЬНО включи этот фрагмент целиком.
3. Между приветствием и прощанием выбери наиболее ключевые и содержательные моменты, чтобы итоговое видео укладывалось в целевую длительность.
4. Фрагменты должны быть логически завершёнными — не обрывай мысль на середине.

Верни ТОЛЬКО валидный JSON-массив в формате:
[
    {{"start": "00:05:10", "end": "00:08:45"}},
    {{"start": "00:12:00", "end": "00:14:30"}}
]

Отвечай ТОЛЬКО валидным JSON, без дополнительного текста."""
```

**Step 2: Verify no other changes needed**

`analyze_highlights()` method passes `transcript`, `duration`, `target_duration` — all already present. No other changes needed in this file.

---

### Task 2: Add `whisperModel` to i18n (all 3 languages)

**Files:**
- Modify: `app/platforms/desktop_windows/src/renderer/i18n/ru.ts`
- Modify: `app/platforms/desktop_windows/src/renderer/i18n/en.ts`
- Modify: `app/platforms/desktop_windows/src/renderer/i18n/zh.ts`

**Step 1: Update ru.ts**

In the `settings` block, after `videoDuration`, add:

```typescript
  settings: {
    title: 'Настройки',
    theme: 'Тема',
    themeLight: 'Светлая',
    themeDark: 'Тёмная',
    themeAuto: 'Авто',
    language: 'Язык',
    whisperModel: 'Скорость транскрибации',
    videoDuration: 'Длина итогового видео',
    save: 'Сохранить',
    saved: 'Настройки сохранены',
  },
```

**Step 2: Update en.ts**

```typescript
  settings: {
    title: 'Settings',
    theme: 'Theme',
    themeLight: 'Light',
    themeDark: 'Dark',
    themeAuto: 'Auto',
    language: 'Language',
    whisperModel: 'Transcription speed',
    videoDuration: 'Output video length',
    save: 'Save',
    saved: 'Settings saved',
  },
```

**Step 3: Update zh.ts**

```typescript
  settings: {
    title: '设置',
    theme: '主题',
    themeLight: '浅色',
    themeDark: '深色',
    themeAuto: '自动',
    language: '语言',
    whisperModel: '转录速度',
    videoDuration: '输出视频长度',
    save: '保存',
    saved: '设置已保存',
  },
```

---

### Task 3: Update SettingsPanel — add Whisper model selector

**Files:**
- Modify: `app/platforms/desktop_windows/src/renderer/components/SettingsPanel.tsx`

**Step 1: Replace entire file content**

```typescript
import React, { useState } from 'react';
import { Settings, Globe, Clock, Zap } from 'lucide-react';
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

export type WhisperModel = 'tiny' | 'small' | 'medium';

const WHISPER_MODEL_OPTIONS: { label: string; value: WhisperModel; hint: string }[] = [
  { label: 'БЫСТРО', value: 'tiny',   hint: 'tiny'   },
  { label: 'СРЕДНЯЯ', value: 'small',  hint: 'small'  },
  { label: 'МЕДЛЕННО', value: 'medium', hint: 'medium' },
];

export const WHISPER_MODEL_KEY = 'transkrib-whisper-model';
export const DEFAULT_WHISPER_MODEL: WhisperModel = 'tiny'; // temporary default for testing

export function getSelectedModel(): WhisperModel {
  const saved = localStorage.getItem(WHISPER_MODEL_KEY) as WhisperModel | null;
  if (saved && ['tiny', 'small', 'medium'].includes(saved)) return saved;
  return DEFAULT_WHISPER_MODEL;
}

export const SettingsPanel: React.FC<Props> = ({ open, onClose }) => {
  const { t, language, setLanguage } = useTranslation();
  const [duration, setDuration] = useState<number>(getSelectedDuration);
  const [whisperModel, setWhisperModel] = useState<WhisperModel>(getSelectedModel);

  const handleDuration = (val: number) => {
    setDuration(val);
    localStorage.setItem(DURATION_STORAGE_KEY, String(val));
  };

  const handleWhisperModel = (val: WhisperModel) => {
    setWhisperModel(val);
    localStorage.setItem(WHISPER_MODEL_KEY, val);
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

        <label style={{ marginTop: '16px' }}><Zap size={14} /> {t('settings.whisperModel')}</label>
        <div className="whisper-model-buttons">
          {WHISPER_MODEL_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              className={`btn-whisper-model ${whisperModel === opt.value ? 'active' : ''}`}
              onClick={() => handleWhisperModel(opt.value)}
              title={opt.hint}
            >
              {opt.label}
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

---

### Task 4: Add CSS for Whisper model buttons

**Files:**
- Modify: `app/platforms/desktop_windows/src/renderer/styles/globals.css`

**Step 1: Find `.duration-buttons` block in CSS, add `.whisper-model-buttons` block right before it**

Search for: `.duration-buttons {`

Add immediately before it:

```css
/* Whisper model selector */
.whisper-model-buttons {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 8px;
}

.btn-whisper-model {
  padding: 6px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-strong);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-fast);
  letter-spacing: 0.03em;
}

.btn-whisper-model:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.btn-whisper-model.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}

```

---

### Task 5: Update api.ts — add whisperModel param

**Files:**
- Modify: `app/platforms/desktop_windows/src/renderer/services/api.ts`

**Step 1: Update `uploadFile` signature and body**

Replace:
```typescript
  async uploadFile(file: File, maxDurationSeconds?: number): Promise<TaskResponse> {
    const form = new FormData();
    form.append('file', file);
    if (maxDurationSeconds) form.append('max_duration_seconds', String(maxDurationSeconds));
```

With:
```typescript
  async uploadFile(file: File, maxDurationSeconds?: number, whisperModel?: string): Promise<TaskResponse> {
    const form = new FormData();
    form.append('file', file);
    if (maxDurationSeconds) form.append('max_duration_seconds', String(maxDurationSeconds));
    if (whisperModel) form.append('whisper_model', whisperModel);
```

**Step 2: Update `submitUrl` signature and body**

Replace:
```typescript
  async submitUrl(url: string, maxDurationSeconds?: number): Promise<TaskResponse> {
    const res = await fetch(`${getBaseUrl()}/api/tasks/url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, max_duration_seconds: maxDurationSeconds ?? null }),
    });
```

With:
```typescript
  async submitUrl(url: string, maxDurationSeconds?: number, whisperModel?: string): Promise<TaskResponse> {
    const res = await fetch(`${getBaseUrl()}/api/tasks/url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, max_duration_seconds: maxDurationSeconds ?? null, whisper_model: whisperModel ?? null }),
    });
```

---

### Task 6: Update App.tsx — pass getSelectedModel()

**Files:**
- Modify: `app/platforms/desktop_windows/src/renderer/App.tsx`

**Step 1: Update import from SettingsPanel**

Replace:
```typescript
import { SettingsPanel, getSelectedDuration } from './components/SettingsPanel';
```
With:
```typescript
import { SettingsPanel, getSelectedDuration, getSelectedModel } from './components/SettingsPanel';
```

**Step 2: Update handleFile**

Replace:
```typescript
      const res = await api.uploadFile(file, maxDuration || undefined);
```
With:
```typescript
      const res = await api.uploadFile(file, maxDuration || undefined, getSelectedModel());
```

**Step 3: Update handleUrl**

Replace:
```typescript
      const res = await api.submitUrl(url, maxDuration || undefined);
```
With:
```typescript
      const res = await api.submitUrl(url, maxDuration || undefined, getSelectedModel());
```

---

### Task 7: Update backend router — accept whisper_model

**Files:**
- Modify: `app/backend/app/routers/standalone_tasks_router.py`

**Step 1: Update UrlSubmission model**

Replace:
```python
class UrlSubmission(BaseModel):
    url: str
    max_duration_seconds: int | None = None
```
With:
```python
class UrlSubmission(BaseModel):
    url: str
    max_duration_seconds: int | None = None
    whisper_model: str | None = None
```

**Step 2: Update upload_video endpoint — add form param and pass to thread**

Add `whisper_model` form parameter and update thread args.

Replace:
```python
async def upload_video(
    file: UploadFile = File(...),
    max_duration_seconds: int | None = Form(None),
):
```
With:
```python
async def upload_video(
    file: UploadFile = File(...),
    max_duration_seconds: int | None = Form(None),
    whisper_model: str | None = Form(None),
):
```

Replace (thread args in upload_video):
```python
    thread = threading.Thread(
        target=_pipeline_runner,
        args=(task_id, str(file_path), file.filename, max_duration_seconds),
        daemon=True,
    )
```
With:
```python
    thread = threading.Thread(
        target=_pipeline_runner,
        args=(task_id, str(file_path), file.filename, max_duration_seconds, whisper_model),
        daemon=True,
    )
```

**Step 3: Update submit_url endpoint — pass whisper_model to thread**

Replace (thread args in submit_url):
```python
    thread = threading.Thread(
        target=_pipeline_runner,
        args=(task_id, url, None, submission.max_duration_seconds),
        daemon=True,
    )
```
With:
```python
    thread = threading.Thread(
        target=_pipeline_runner,
        args=(task_id, url, None, submission.max_duration_seconds, submission.whisper_model),
        daemon=True,
    )
```

---

### Task 8: Update standalone_tasks.py — hot-swap Whisper model

**Files:**
- Modify: `app/backend/app/workers/standalone_tasks.py`

**Step 1: Update `_get_services` to accept whisper_model and hot-swap**

Replace:
```python
def _get_services():
    """
    Lazily initializes and returns singleton services.

    Same pattern as workers/tasks.py _get_services().
    Thread-safe via lock.
    """
    global _ffmpeg, _transcriber, _analyzer, _storage

    with _services_lock:
        if _ffmpeg is None:
            logger.info("Initializing FFmpegService...")
            _ffmpeg = FFmpegService(settings.ffmpeg_path)

        if _transcriber is None:
            logger.info(f"Initializing TranscriptionService (model: {settings.whisper_model})...")
            _transcriber = TranscriptionService(settings.whisper_model, settings.whisper_cache_dir)
            # Model loading is deferred until first use (transcriber.transcribe calls ensure_model)
            # This avoids 30-60s startup delay
```
With:
```python
def _get_services(whisper_model: str | None = None):
    """
    Lazily initializes and returns singleton services.

    Same pattern as workers/tasks.py _get_services().
    Thread-safe via lock.
    """
    global _ffmpeg, _transcriber, _analyzer, _storage

    with _services_lock:
        if _ffmpeg is None:
            logger.info("Initializing FFmpegService...")
            _ffmpeg = FFmpegService(settings.ffmpeg_path)

        requested_model = whisper_model or settings.whisper_model
        if _transcriber is None or _transcriber.model_name != requested_model:
            logger.info(f"Initializing TranscriptionService (model: {requested_model})...")
            _transcriber = TranscriptionService(requested_model, settings.whisper_cache_dir)
            # Model loading is deferred until first use (transcriber.transcribe calls ensure_model)
            # This avoids 30-60s startup delay
```

**Step 2: Update `run_video_task` signature and _get_services call**

Replace:
```python
def run_video_task(task_id: str, file_path: str, original_name: str, max_duration_seconds: int | None = None):
```
With:
```python
def run_video_task(task_id: str, file_path: str, original_name: str, max_duration_seconds: int | None = None, whisper_model: str | None = None):
```

Replace in `run_video_task`:
```python
    ffmpeg, transcriber, analyzer, storage, progress = _get_services()
```
With:
```python
    ffmpeg, transcriber, analyzer, storage, progress = _get_services(whisper_model)
```

**Step 3: Update `run_url_task` signature and _get_services call**

Replace:
```python
def run_url_task(task_id: str, url: str, max_duration_seconds: int | None = None):
```
With:
```python
def run_url_task(task_id: str, url: str, max_duration_seconds: int | None = None, whisper_model: str | None = None):
```

Replace in `run_url_task`:
```python
    ffmpeg, transcriber, analyzer, storage, progress = _get_services()
```
With:
```python
    ffmpeg, transcriber, analyzer, storage, progress = _get_services(whisper_model)
```

---

### Task 9: Add sound wave animation — CSS

**Files:**
- Modify: `app/platforms/desktop_windows/src/renderer/styles/globals.css`

**Step 1: Add sound wave CSS after `.proc-bar-fill` block (after line ~1529)**

Find this line in globals.css:
```css
/* Submit error */
```

Insert immediately before it:

```css
/* Sound wave animation (shown during transcription) */
.proc-wave {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
  height: 20px;
  margin-top: 6px;
}

.proc-wave-bar {
  width: 3px;
  height: 4px;
  border-radius: 2px;
  background: var(--color-primary);
  animation: proc-wave-anim 0.9s ease-in-out infinite;
}

.proc-wave-bar:nth-child(1) { animation-delay: 0s; }
.proc-wave-bar:nth-child(2) { animation-delay: 0.12s; }
.proc-wave-bar:nth-child(3) { animation-delay: 0.24s; }
.proc-wave-bar:nth-child(4) { animation-delay: 0.36s; }
.proc-wave-bar:nth-child(5) { animation-delay: 0.48s; }

@keyframes proc-wave-anim {
  0%, 100% { height: 4px; opacity: 0.5; }
  50%       { height: 18px; opacity: 1; }
}

```

---

### Task 10: Add sound wave animation — JSX

**Files:**
- Modify: `app/platforms/desktop_windows/src/renderer/components/ProcessingProgress.tsx`

**Step 1: Add wave under active Mic icon**

In the stage render loop, after the `proc-stage-pct` span, add the wave only when `active && stage.key === 'transcribing'`:

Replace the inner stage div content block:
```tsx
              <div className={`proc-stage ${done ? 'done' : active ? 'active' : 'pending'}`}>
                <div className="proc-stage-icon">
                  {done ? <Check size={16} /> : <Icon size={16} />}
                </div>
                <span className="proc-stage-label">{stage.label}</span>
                {active && <span className="proc-stage-pct">{Math.round(progress)}%</span>}
              </div>
```
With:
```tsx
              <div className={`proc-stage ${done ? 'done' : active ? 'active' : 'pending'}`}>
                <div className="proc-stage-icon">
                  {done ? <Check size={16} /> : <Icon size={16} />}
                </div>
                <span className="proc-stage-label">{stage.label}</span>
                {active && <span className="proc-stage-pct">{Math.round(progress)}%</span>}
                {active && stage.key === 'transcribing' && (
                  <div className="proc-wave">
                    <div className="proc-wave-bar" />
                    <div className="proc-wave-bar" />
                    <div className="proc-wave-bar" />
                    <div className="proc-wave-bar" />
                    <div className="proc-wave-bar" />
                  </div>
                )}
              </div>
```

---

### Task 11: Rebuild backend.exe and installer

**Step 1: Run build_all.bat**

```
cd C:\Users\Admin\OneDrive\Desktop\Cursor\app
build_all.bat
```

Expected output:
- `[1/3]` — cleans and rebuilds `backend.exe` via PyInstaller (~5–15 min)
- `[2/3]` — npm install + Electron build
- `[3/3]` — NSIS universal installer

Output files in `app/platforms/desktop_windows/release/`:
- `Transkrib-Setup-1.0.0.exe` — universal installer

**Step 2: Install and test**

1. Run `Transkrib-Setup-1.0.0.exe`
2. Open settings → verify БЫСТРО/СРЕДНЯЯ/МЕДЛЕННО buttons appear
3. Submit a YouTube URL → during transcription step, verify sound wave animates
4. Verify result video starts with speaker greeting (if present) and ends with farewell
