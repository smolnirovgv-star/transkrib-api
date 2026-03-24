# Transkrib SmartCut AI — Project Context

> Вставляй этот файл в начало каждого нового чата с Claude Code.
> Дата последнего обновления: 2026-03-22

---

## 1. Что такое проект

**Transkrib SmartCut AI** — десктопное приложение для Windows (Electron + FastAPI), которое:
- принимает длинное видео (файл или YouTube URL)
- транскрибирует через faster-whisper (локально)
- выбирает ключевые моменты через Claude API
- рендерит MP4-резюме с субтитрами через FFmpeg

Целевая аудитория: люди, которые работают с вебинарами, интервью, подкастами.

**Render.com API** — параллельно поднят облачный бэкенд для web-версии:
- GitHub репо: `https://github.com/smolnirovgv-star/transkrib-api`
- render.yaml в корне проекта (`rootDir: backend`)
- Python 3.11.9 (runtime.txt)

---

## 2. Структура проекта

```
Transkrib_SmartCut_AI/
├── backend/                         ← Python FastAPI сервер
│   ├── standalone_server.py         ← точка входа PyInstaller + Render.com
│   ├── backend.spec                 ← PyInstaller spec
│   ├── requirements.txt             ← минимальный (для Render.com)
│   ├── requirements-standalone.txt  ← полный (для PyInstaller)
│   ├── runtime.txt                  ← python-3.11.9 (Render.com)
│   ├── render.yaml                  ← конфиг Render сервиса
│   ├── .gitignore                   ← исключает .env, storage/, *.pt, dist/
│   ├── app/
│   │   ├── config.py                ← Settings (pydantic), пути к storage
│   │   ├── license.py               ← LicenseManager (офлайн HMAC проверка)
│   │   ├── trial.py                 ← TrialManager (мульти-слойная защита)
│   │   ├── fingerprint.py           ← сбор hardware fingerprint
│   │   ├── pipeline.py              ← основной пайплайн: Whisper→pause_detector→highlight_scorer→FFmpeg
│   │   ├── models/                  ← Pydantic схемы
│   │   ├── routers/
│   │   │   ├── transcript.py        ← GET /api/transcript/{filename} + /download + /highlights
│   │   │   └── export.py            ← POST /export (multi-path lookup)
│   │   ├── services/
│   │   │   ├── transcription_service.py  ← faster-whisper (WhisperModel, device='cpu')
│   │   │   ├── pause_detector.py    ← анализ пауз > 0.8 сек
│   │   │   ├── highlight_scorer.py  ← оценка фраз 1-10 через Claude API
│   │   │   └── preview_service.py   ← генерация превью через Stability AI
│   │   ├── workers/                 ← standalone_tasks.py (threading, без Celery)
│   │   └── websocket/               ← WebSocket progress push
│   └── .env                         ← APP_ANTHROPIC_API_KEY (не в git!)
│
├── platforms/
│   └── desktop_windows/             ← Electron app (основная платформа)
│       ├── src/
│       │   ├── main/
│       │   │   ├── index.ts         ← IPC handlers + app:saveTranscript
│       │   │   └── backend.ts       ← запуск backend.exe как subprocess
│       │   └── renderer/
│       │       ├── App.tsx          ← экраны: conditional render (НЕ carousel)
│       │       ├── theme.tsx        ← useTheme(), localStorage
│       │       ├── i18n/            ← ru / en / zh
│       │       ├── components/
│       │       │   ├── TitleBar.tsx
│       │       │   ├── AppHeader.tsx
│       │       │   ├── AppFooter.tsx          ← TG: t.me/video_transkrib
│       │       │   ├── SetupWizard.tsx
│       │       │   ├── BackendStartup.tsx
│       │       │   ├── DropZone.tsx
│       │       │   ├── UrlInput.tsx
│       │       │   ├── HowItWorks.tsx         ← статическая сетка 3×2 (без carousel)
│       │       │   ├── Pricing.tsx
│       │       │   ├── AuthModal.tsx
│       │       │   ├── StepCards.tsx
│       │       │   ├── ProcessingProgress.tsx
│       │       │   ├── ResultGallery.tsx      ← Download (мгновенно) + Export (modal)
│       │       │   ├── ExportModal.tsx
│       │       │   ├── TranscriptViewer.tsx   ← поиск + фильтр важных + highlights
│       │       │   ├── SegmentTimeline.tsx    ← toggle include/exclude сегментов
│       │       │   ├── VideoHistory.tsx
│       │       │   ├── SettingsPanel.tsx
│       │       │   └── DemoModal.tsx
│       │       ├── hooks/
│       │       │   ├── useAuth.ts
│       │       │   ├── useTaskProgress.ts
│       │       │   └── useWebSocket.ts
│       │       ├── lib/
│       │       │   └── supabaseClient.ts
│       │       └── styles/
│       │           └── globals.css
│       ├── electron-builder.yml
│       └── package.json
│
├── render.yaml                      ← rootDir: backend (для Render.com)
├── supabase/migrations/
├── tools/
│   ├── keygen.py
│   ├── generate_keys.bat
│   └── reset_trial.py
├── build_all.bat
└── rebuild_installer.bat
```

---

## 3. Технологический стек

| Слой | Технология |
|------|-----------|
| Backend | Python 3.11, FastAPI, Uvicorn, threading |
| Транскрипция | **faster-whisper** (локально, модель `tiny`, device='cpu', compute_type='int8') |
| AI-анализ | Anthropic Claude API |
| Превью | Stability AI API (Stable Image Core) |
| Видео | FFmpeg (bundled), yt-dlp (bundled) |
| Desktop shell | Electron 28, TypeScript |
| UI | React 18, TypeScript, CSS (без UI-фреймворка) |
| Auth | Supabase (email/password) |
| Лицензии | Офлайн HMAC-подпись (`TRSK-PLAN-XXXX-XXXX-HMAC8`) |
| i18n | Самописный контекст (ru/en/zh) |
| Тема | CSS vars + `data-theme` (light/dark) |
| Сборка | PyInstaller (backend.exe) + electron-builder (NSIS x64+ia32) |
| Облако | Render.com (Web Service, Python runtime) |

---

## 4. Ключевые архитектурные решения

### Pipeline обработки видео
```
Видео/URL
    ↓ Audio extraction (ffmpeg — сначала аудио для ускорения)
    ↓ faster-whisper → сегменты с timestamps (генератор)
    ↓ pause_detector → фразы, разбитые по паузам > 0.8 сек
    ↓ highlight_scorer → оценка каждой фразы 1-10 (Claude API)
    ↓ Фильтр score ≥ 6 + группировка в клипы 10-30 сек
    ↓ Приветствие/прощание — всегда включены (первые/последние 30 сек)
    ↓ Параллельный FFmpeg → нарезка клипов
    ↓ Результат: MP4 + _segments.json (кэш)
```

### faster-whisper API (отличие от openai-whisper)
```python
from faster_whisper import WhisperModel
model = WhisperModel("tiny", device="cpu", compute_type="int8")
segments_gen, info = model.transcribe(audio_path)  # возвращает (генератор, info)
for seg in segments_gen:
    seg.start, seg.end, seg.text  # атрибуты объекта, не dict
```
Кэш модели: `HF_HOME` env → `storage/hf_models/`

### Навигация между экранами (App.tsx)
НЕ carousel/translateX. Условный рендер:
```tsx
{screen === 0 && (<div className="screen-main">...</div>)}
{screen === 1 && <div className="screen-how"><HowItWorks /></div>}
{screen === 2 && <div className="screen-prices"><Pricing /></div>}
```

### TranscriptViewer
- Всегда видимая строка поиска `.transcript-search-bar`
- Кнопки: Все / Важные
- Загружает highlights: `GET /api/transcript/{filename}/highlights`
- Fallback важных: `seg.score >= 6` если highlights пусты
- Подсветка текста: `highlightText()` helper (жёлтый фон)

### ResultGallery кнопки
- **Download** — мгновенно, через `electronAPI.downloadResult` (без диалога)
- **Export** — открывает ExportModal с настройками (формат/качество/разрешение/субтитры)

### HowItWorks
Статическая сетка 3 колонки, 6 шагов. Никакого useState, animation, i18n — plain JSX.

### standalone_server.py (PORT/HOST)
```python
PORT = int(os.environ.get("PORT", os.environ.get("TRANSKRIB_PORT", "8000")))
HOST = os.environ.get("HOST", "127.0.0.1")
```
Render.com задаёт HOST=0.0.0.0 через render.yaml.

### Polling (useTaskProgress.ts)
- Интервал: **1000ms** (было 1500ms)
- Остановка: при `completed` или `failed` — НЕ перезапускается

### Export path fallback (export.py)
3 кандидата пути, русское сообщение об ошибке.

---

## 5. Render.com деплой

### Файлы конфигурации

**`render.yaml`** (корень проекта):
```yaml
services:
  - type: web
    name: transkrib-api
    runtime: python
    rootDir: backend
    buildCommand: pip install -r requirements.txt
    startCommand: python standalone_server.py
    envVars:
      - key: HOST
        value: '0.0.0.0'
      - key: APP_WHISPER_MODEL
        value: tiny
      - key: APP_ANTHROPIC_API_KEY
        sync: false
```

**`backend/runtime.txt`**: `python-3.11.9`

**`backend/requirements.txt`** (минимальный для Render):
```
fastapi==0.115.0
uvicorn[standard]==0.30.0
python-multipart==0.0.9
pydantic==2.9.2
pydantic-settings==2.5.2
python-dotenv==1.0.1
aiofiles==24.1.0
anthropic==0.39.0
yt-dlp>=2024.10.22
faster-whisper==1.0.3
httpx==0.27.0
```

### GitHub репозиторий
- URL: `https://github.com/smolnirovgv-star/transkrib-api`
- Ветка: `main`
- .gitignore исключает: `.env*`, `storage/`, `*.pt`, `dist/`, `build/`

---

## 6. UI / UX

### Экраны (App.tsx)
```
screen-main   ← Hero + Upload (DropZone / UrlInput)
screen-how    ← HowItWorks (6 шагов, 3 колонки, padding-top: 20px)
screen-prices ← Pricing (Trial / Base / Standard / Pro, padding-top: 20px)
```

### Состояния приложения
```
BackendStartup → SetupWizard (лицензия/trial) → Главная
    ↓ загрузка видео
Processing → ResultGallery
    ↓ кнопки: Download | Экспорт | 📄 Транскрипт ▾ | ↻ Превью
TranscriptViewer (с поиском, фильтром, highlights)
```

### Тарифы
4 плана: Trial (7 дней), Base ($5), Standard ($19/мес), Pro ($99/год)

---

## 7. Текущий статус (2026-03-22)

### ✅ Выполнено в сессиях pr.58–pr.76

**Производительность:**
- pr.58: Polling 1000ms, стоп при completed/failed

**TranscriptViewer (pr.59, pr.60):**
- Highlights endpoint `/api/transcript/{filename}/highlights`
- Поиск + фильтр Все/Важные (всегда видимый)
- SegmentTimeline toggle include/exclude
- Export path 3-кандидата fallback

**UI результатов (pr.61):**
- Download (мгновенный) отделён от Export (модал)

**HowItWorks (pr.62–pr.68):**
- Заменён carousel на статическую сетку 3×2
- Убрана цепочка overflow:hidden (screens-wrapper → screens-track)
- App.tsx: conditional render вместо translateX
- padding-top: 20px для screen-how и screen-prices
- CSS консолидирован (нет дублей)

**Backend (pr.69):**
- openai-whisper → faster-whisper==1.0.3
- WhisperModel("tiny", device="cpu", compute_type="int8")
- pipeline.py: iterdir() вместо glob("*.pt")
- config.py: модель по умолчанию "tiny"

**Render.com деплой (pr.70–pr.76):**
- backend/render.yaml с HOST=0.0.0.0
- standalone_server.py: PORT/HOST из env
- GitHub repo: smolnirovgv-star/transkrib-api (git init + push)
- root render.yaml с rootDir: backend
- backend/runtime.txt: python-3.11.9
- backend/requirements.txt: минимальный (убраны supabase, ffmpeg-python)

### 🏁 СТАТУС: ГОТОВ К ПЕРЕСБОРКЕ

Нужна пересборка backend.exe (faster-whisper вместо openai-whisper):
```
build_all.bat
```
Или только Electron (без PyInstaller):
```
rebuild_installer.bat
```

---

## 8. Известные ограничения и gotchas

### OneDrive EEXIST
Файлы проекта на OneDrive. Инструмент Edit/Write иногда падает с EEXIST.
**Workaround**: писать в `C:/Users/Admin/AppData/Local/Temp/`, затем `shutil.copy2()`.

### TypeScript — без бэктиков в строках
Использовать одинарные кавычки. Бэктики (template literals) могут вызывать проблемы.

### faster-whisper vs openai-whisper
- Возвращает `(generator, info)`, а не dict
- Атрибуты: `seg.start`, `seg.end`, `seg.text` (не `seg["start"]`)
- Модель в HF_HOME, не в `~/.cache/whisper/`

### PyInstaller + Windows 11
- Антивирус может блокировать backend.exe
- HKLM запись требует прав администратора при первом запуске

### Render.com — ограничения
- Whisper модель скачивается при каждом cold start (нет persistent storage)
- APP_ANTHROPIC_API_KEY нужно задать вручную в Dashboard (sync: false)
- faster-whisper требует ctranslate2 — большой пакет, медленный build

---

## 9. Незакрытые задачи

1. **Пересборка backend.exe** — после замены на faster-whisper (pr.69), запустить `build_all.bat`
2. **Тестирование Render.com** — проверить что деплой проходит с текущим requirements.txt
3. **Тестирование на чистой машине** — fresh install не проверяли
4. **macOS платформа** — scaffold есть, не разрабатывалась

---

## 10. Команды разработчика

```bash
# Dev режим (Vite + Electron)
cd platforms/desktop_windows && npx vite
# или
cd platforms/desktop_windows && npm run dev

# Backend в dev режиме
cd backend && python standalone_server.py

# Typecheck
cd platforms/desktop_windows && npm run typecheck

# Генерация лицензионных ключей
cd tools && python keygen.py

# Сброс trial
python tools/reset_trial.py

# Полная пересборка (PyInstaller + Electron + NSIS)
build_all.bat

# Только Electron installer (x64 + ia32 + universal NSIS)
rebuild_installer.bat
```

---

## 11. Supabase проект

- **URL**: `https://aakxqjpyikhjzkfvwppu.supabase.co`
- **Dashboard**: `https://supabase.com/dashboard/project/aakxqjpyikhjzkfvwppu`
- Email confirmation: **отключён** ✅
- Таблица user_licenses: **применена** ✅

---

## 12. API ключи (.env файлы — не в git!)

### backend/.env
```
APP_ANTHROPIC_API_KEY=sk-ant-...
APP_STABILITY_API_KEY=sk-...
APP_WHISPER_MODEL=tiny
APP_CLAUDE_MODEL=claude-sonnet-4-5-20250929
```

### platforms/desktop_windows/.env (Vite)
```
VITE_SUPABASE_URL=https://aakxqjpyikhjzkfvwppu.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
```

### Render.com Dashboard
`APP_ANTHROPIC_API_KEY` нужно задать вручную (sync: false в render.yaml).

---

## 13. Лицензионная система

- Формат ключа: `TRSK-{PLAN}-{XXXX}-{XXXX}-{HMAC8}`
- Планы: BASE (10 дней), STND (30 дней), PREM (365 дней)
- Офлайн HMAC-SHA256 проверка (без интернета)
- `license.key` — JSON: `{"key": "...", "activated": "ISO", "days": N, "plan": "BASE"}`
- Генерация: `tools/keygen.py` + `tools/generate_keys.bat`

### Trial система
- 7 дней, 3 видео/день, до 30 минут на видео
- Мульти-слойная защита: файл + HKCU + HKLM registry
- HMAC-подпись на основе MachineGuid
