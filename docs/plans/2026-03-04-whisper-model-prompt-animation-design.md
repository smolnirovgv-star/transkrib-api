# Design: Whisper Model Selector, Prompt Improvement, Transcription Animation

**Date:** 2026-03-04

## Task 1 — Improve Claude API Prompt

### Problem
Current `HIGHLIGHTS_PROMPT` selects key moments but has no instruction to always include speaker greeting (intro) and farewell (outro).

### Design
Update `HIGHLIGHTS_PROMPT` in `app/backend/app/services/analysis_service.py`:
1. If video starts with a greeting (0:00–2:00) — always include it
2. If video ends with a farewell (last 2 minutes) — always include it
3. Fill remaining target duration with the most key/informative moments in between

---

## Task 2 — Whisper Model Selector in Settings

### Design

**Frontend:**
- `SettingsPanel.tsx`: Add 3 buttons (БЫСТРО/tiny, СРЕДНЯЯ/small, МЕДЛЕННО/medium)
- `WHISPER_MODEL_KEY = 'transkrib-whisper-model'`
- `DEFAULT_MODEL = 'tiny'` (temporary for testing, change to 'small' later)
- Export `getSelectedModel()` — same pattern as `getSelectedDuration()`
- i18n keys: `settings.whisperModel` (label) in ru/en/zh

**api.ts:**
- Add `whisperModel?: string` param to `uploadFile(file, maxDuration, whisperModel)`
- Add `whisperModel?: string` param to `submitUrl(url, maxDuration, whisperModel)`
- Pass as `whisper_model` field in request body/form

**App.tsx:**
- Import `getSelectedModel` from SettingsPanel
- Pass `getSelectedModel()` to `api.uploadFile` and `api.submitUrl`

**Backend:**
- `standalone_tasks_router.py`:
  - `UrlSubmission`: add `whisper_model: str | None = None`
  - `/upload` endpoint: add `whisper_model: str | None = Form(None)`
  - Pass `whisper_model` to pipeline runner thread args
- `standalone_tasks.py`:
  - `run_video_task(task_id, file_path, name, max_duration, whisper_model=None)`
  - `run_url_task(task_id, url, max_duration, whisper_model=None)`
  - `_get_services(whisper_model=None)`: compare `_transcriber.model_name` vs `requested_model`, reinit if different

---

## Task 3 — Transcription Animation (Sound Wave)

### Design
In `ProcessingProgress.tsx`, when `state === 'transcribing'`:
- Render 5 animated bars (`.proc-wave` + `.proc-wave-bar`) under the Mic icon
- Pure CSS `@keyframes proc-wave-bar` animation, each bar has different `animation-delay`
- Bars animate height between ~30% and 100% with easing

**CSS additions to `globals.css`:**
- `.proc-wave`: flex row, gap 2px, height 20px, align-items center
- `.proc-wave-bar`: width 3px, border-radius 2px, background primary color, animation
- `@keyframes proc-wave-bar`: `0%,100% { height: 4px } 50% { height: 16px }`
- Each of 5 bars: `animation-delay: 0s, 0.1s, 0.2s, 0.3s, 0.4s`

---

## Files Changed

| File | Change |
|------|--------|
| `app/backend/app/services/analysis_service.py` | Update HIGHLIGHTS_PROMPT |
| `app/platforms/desktop_windows/src/renderer/components/SettingsPanel.tsx` | Add whisper model buttons |
| `app/platforms/desktop_windows/src/renderer/i18n/ru.ts` | Add settings.whisperModel |
| `app/platforms/desktop_windows/src/renderer/i18n/en.ts` | Add settings.whisperModel |
| `app/platforms/desktop_windows/src/renderer/i18n/zh.ts` | Add settings.whisperModel |
| `app/platforms/desktop_windows/src/renderer/services/api.ts` | Add whisperModel param |
| `app/platforms/desktop_windows/src/renderer/App.tsx` | Pass getSelectedModel() |
| `app/backend/app/routers/standalone_tasks_router.py` | Add whisper_model param |
| `app/backend/app/workers/standalone_tasks.py` | Model hot-swap in _get_services |
| `app/platforms/desktop_windows/src/renderer/components/ProcessingProgress.tsx` | Sound wave JSX |
| `app/platforms/desktop_windows/src/renderer/styles/globals.css` | Sound wave CSS |
