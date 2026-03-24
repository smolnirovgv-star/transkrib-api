# Transkrib SmartCut AI — Project Context

> Вставляй этот файл в начало каждого нового чата с Claude Code.
> Дата последнего обновления: 2026-03-13

---

## 1. Что такое проект

**Transkrib SmartCut AI** — десктопное приложение для Windows (Electron + FastAPI), которое:
- принимает длинное видео (файл или YouTube URL)
- транскрибирует через Whisper
- выбирает ключевые моменты через Claude API
- рендерит MP4-резюме с субтитрами через FFmpeg

Целевая аудитория: люди, которые работают с вебинарами, интервью, подкастами.

---

## 2. Структура проекта

```
Transkrib_SmartCut_AI/
├── backend/                         ← Python FastAPI сервер
│   ├── standalone_server.py         ← точка входа PyInstaller (backend.exe)
│   ├── backend.spec                 ← PyInstaller spec
│   ├── requirements-standalone.txt
│   ├── app/
│   │   ├── config.py                ← Settings (pydantic), пути к storage
│   │   ├── license.py               ← LicenseManager (офлайн HMAC проверка)
│   │   ├── trial.py                 ← TrialManager (мульти-слойная защита)
│   │   ├── fingerprint.py           ← сбор hardware fingerprint
│   │   ├── pipeline.py              ← основной пайплайн обработки
│   │   ├── models/                  ← Pydantic схемы
│   │   ├── routers/                 ← FastAPI роутеры
│   │   ├── services/                ← TranscriptionService, FFmpegService и др.
│   │   ├── workers/                 ← standalone_tasks.py (threading, без Celery)
│   │   └── websocket/               ← WebSocket progress push
│   └── .env                         ← APP_ANTHROPIC_API_KEY (extraResources)
│
├── platforms/
│   └── desktop_windows/             ← Electron app (основная платформа)
│       ├── src/
│       │   ├── main/                ← Electron main process (TypeScript)
│       │   │   ├── index.ts         ← точка входа main, IPC handlers
│       │   │   └── backend.ts       ← запуск backend.exe как subprocess
│       │   └── renderer/            ← React UI
│       │       ├── App.tsx          ← корневой компонент, логика экранов
│       │       ├── theme.tsx        ← ThemeProvider (light/dark, localStorage)
│       │       ├── i18n/            ← локализация (ru/en/zh)
│       │       │   ├── ru.ts        ← master (все ключи здесь)
│       │       │   ├── en.ts
│       │       │   ├── zh.ts
│       │       │   └── index.ts     ← useTranslation() hook, LanguageProvider
│       │       ├── components/
│       │       │   ├── TitleBar.tsx        ← язык + тема кнопки
│       │       │   ├── AppHeader.tsx       ← навигация, login/start кнопки
│       │       │   ├── AppFooter.tsx       ← копирайт, ссылки
│       │       │   ├── SetupWizard.tsx     ← онбординг (лицензия / trial)
│       │       │   ├── BackendStartup.tsx  ← ожидание backend.exe (+ browser fallback)
│       │       │   ├── DropZone.tsx        ← drag-and-drop загрузка файла
│       │       │   ├── UrlInput.tsx        ← ввод YouTube/видео URL
│       │       │   ├── HowItWorks.tsx      ← страница "как работает"
│       │       │   ├── Pricing.tsx         ← страница тарифов (Trial/Base/Std/Pro)
│       │       │   ├── AuthModal.tsx       ← login/register/forgot (Supabase)
│       │       │   ├── StepCards.tsx       ← прогресс шагов обработки
│       │       │   ├── ProcessingProgress.tsx ← прогресс для URL-задач
│       │       │   ├── ResultGallery.tsx   ← результаты (видео + субтитры)
│       │       │   ├── SettingsPanel.tsx   ← настройки (язык, модель, длина)
│       │       │   └── DemoModal.tsx       ← демо-видео модал
│       │       ├── hooks/
│       │       │   ├── useAuth.ts          ← Supabase auth state
│       │       │   ├── useTaskProgress.ts  ← polling + WS прогресс задачи
│       │       │   └── useWebSocket.ts     ← WebSocket обёртка
│       │       ├── lib/
│       │       │   └── supabaseClient.ts   ← createClient (graceful degrade без .env)
│       │       └── styles/
│       │           └── globals.css         ← все стили (BEM-like, CSS vars темы)
│       ├── electron-builder.yml            ← NSIS installer config
│       └── package.json
│
├── supabase/
│   ├── config.toml
│   └── migrations/
│       └── 20260313140631_create_user_licenses.sql  ← таблица user_licenses + RLS
│
├── tools/
│   ├── keygen.py           ← генератор лицензионных ключей TRSK-*
│   ├── generate_keys.bat   ← запускалка keygen.py
│   └── reset_trial.py      ← утилита для сброса trial (разработка)
│
├── build_all.bat           ← полная пересборка: PyInstaller + Electron + NSIS
└── rebuild_installer.bat   ← только Electron: npm + electron-builder + universal NSIS
```

---

## 3. Технологический стек

| Слой | Технология |
|------|-----------|
| Backend | Python 3.11, FastAPI, Uvicorn, threading (без Redis/Celery) |
| Транскрипция | OpenAI Whisper (локально, модель `base` или `small`) |
| AI-анализ | Anthropic Claude API (`claude-*` модели) |
| Видео | FFmpeg (bundled в PyInstaller), yt-dlp (bundled) |
| Desktop shell | Electron 28, TypeScript |
| UI | React 18, TypeScript, CSS (без UI-фреймворка) |
| Auth | Supabase (email/password) |
| Лицензии | Офлайн HMAC-подпись (`TRSK-PLAN-XXXX-XXXX-HMAC8`) |
| i18n | Самописный контекст (ru/en/zh) |
| Тема | CSS vars + `data-theme` атрибут (light/dark) |
| Сборка | PyInstaller (backend.exe) + electron-builder (NSIS) |

---

## 4. Ключевые архитектурные решения

### Backend как subprocess
- Electron main process (`backend.ts`) запускает `backend.exe` как child process
- Перед запуском инжектирует env: `APP_STORAGE_DIR`, `APP_ANTHROPIC_API_KEY`
- Все данные изолированы в `%APPDATA%\Transkrib\storage\` — ничего не пишет в системные папки
- Backend слушает на `localhost:<random_port>`, порт передаётся в renderer через IPC

### Storage isolation (полностью реализовано)
```
%APPDATA%\Transkrib\storage\
├── uploads/          ← загруженные видео
├── processing/       ← промежуточные файлы FFmpeg + транскрипты
├── results/          ← готовые MP4
├── whisper_models/   ← Whisper .pt файлы (~461 MB для base)
├── temp/             ← tempfile.tempdir переопределён сюда
├── torch_models/     ← TORCH_HOME
├── numba_cache/      ← NUMBA_CACHE_DIR
├── tiktoken_cache/   ← TIKTOKEN_CACHE_DIR
├── hf_models/        ← HF_HOME
├── logs/             ← backend.log (только frozen/prod)
└── .license/
    └── license.key   ← JSON {key, activated, days, plan}
```

### Trial система (мульти-слойная защита)
- **7 дней**, **3 видео/день**, **до 30 минут** на видео
- Хранение: файл `trial.dat` + HKCU registry + HKLM registry (admin, write-once)
- HMAC-подпись данных на основе MachineGuid (machine-bound)
- Обнаружение отката часов (интернет-время: worldtimeapi.org, cloudflare, google)
- Обнаружение bypass: >2 hardware компонентов изменились → permanent block
- Security log: `%APPDATA%\Transkrib\security.log`
- State machine: `new → active → warning (≤2 дней) → expired | blocked`

### Лицензионная система
- Формат: `TRSK-{PLAN}-{XXXX}-{XXXX}-{HMAC8}`
- Планы: `BASE` (10 дней), `STND` (30 дней), `PREM` (365 дней)
- Проверка офлайн через HMAC-SHA256
- Генерация: `tools/keygen.py` + `tools/generate_keys.bat`
- Ключи сохраняются в `Transkrib_Keys/plan_basic/`, `plan_standard/`, `plan_pro/`

### Supabase Auth
- Проект: `aakxqjpyikhjzkfvwppu.supabase.co`
- `.env` (в корне `desktop_windows/`): `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
- `supabaseClient.ts` gracefully деградирует если env не задан (`supabaseConfigured = false`)
- Auth state: `useAuth()` hook → user/session/signOut
- Таблица `user_licenses` с RLS (миграция: `supabase/migrations/20260313140631_create_user_licenses.sql`)
- Email confirmation: **отключён** в Supabase Dashboard (для тестирования)

### i18n
- Master-файл: `i18n/ru.ts` (все ключи)
- `en.ts`, `zh.ts` реализуют `TranslationKeys` (тип `DeepString<typeof ru>` — не literal)
- `useTranslation()` → `{ t, language, setLanguage }`
- Язык сохраняется в localStorage, переключение мгновенное без перезагрузки
- Все компоненты используют `t()` — hardcoded строк на русском нет

### Browser-mode fallback (для разработки без Electron)
- `BackendStartup`: если `!window.electronAPI` — немедленно вызывает `onReady()`
- `handleTrialStart`: если `!window.electronAPI` — сет mock `trialStatus: active`
- Dev-сервер: `npm run dev` в `platforms/desktop_windows/`

---

## 5. UI / UX

### Структура экранов (3 слайда)
```
Screen 0: Главная      ← Hero + Upload (DropZone / UrlInput)
Screen 1: Как работает ← HowItWorks (3 шага)
Screen 2: Цены         ← Pricing (Trial / Base / Standard / Pro)
```

Navigation: горизонтальный слайдер (`screens-track`), стрелки + dots внизу.

### Состояния приложения
```
BackendStartup → (backend готов)
  ↓
isLicensed=null → loading spinner
  ↓
!isLicensed && !trialAllowed → SetupWizard (онбординг)
  ↓
Основной интерфейс:
  Phase: input → processing → result
```

### Темы
- `data-theme="light"` / `data-theme="dark"` на `<html>`
- CSS vars: `--bg`, `--surface`, `--border`, `--text`, `--text-muted`, `--accent`
- Светлая тема включена по умолчанию

### Pricing карточки
4 плана: Trial (бесплатно, 7 дней), Base ($5), Standard ($19/мес, recommended), Pro ($99/год)
Важно: в light теме кнопка recommended карточки имеет `color: #0F172A` (тёмный текст)

---

## 6. Сборка и деплой

### Разработка (browser preview)
```bash
cd platforms/desktop_windows
npm run dev
# → http://localhost:5173 (React only, без Electron и backend)
```

### Разработка (полный Electron)
```bash
cd platforms/desktop_windows
npm run dev
# Запускает: vite + tsc watch + electron (после того как vite готов)
```

### Полная пересборка (релиз)
```bat
build_all.bat
# [1/3] Очистка dist/backend и build/backend
# [2/3] PyInstaller backend.spec → backend/dist/backend/backend.exe (5-15 мин)
# [3/3] rebuild_installer.bat → npm install + npm run build + electron-builder + NSIS
```

### Только Electron (без пересборки backend)
```bat
rebuild_installer.bat
# npm install (clean) + npm run build
# electron-builder --win --x64 --ia32
# makensis universal wrapper
# Результат: release/Transkrib-Setup-1.0.0.exe (universal)
#            release/Transkrib-Setup-1.0.0-x64.exe
#            release/Transkrib-Setup-1.0.0-ia32.exe
#            release/Transkrib-Setup-b001-2026-03-13.exe (versioned copy)
```

### PyInstaller
- Spec: `backend/backend.spec`
- Бандлит: FFmpeg binaries, yt-dlp.exe, все Python deps
- Выход: `backend/dist/backend/backend.exe` + `_internal/`
- Electron-builder копирует в `resources/backend/` через `extraResources`

---

## 7. Ключевые файлы и их роль

| Файл | Назначение |
|------|-----------|
| `backend/standalone_server.py` | FastAPI app factory, изоляция путей, логирование |
| `backend/app/trial.py` | TrialManager: состояние, защита, daily limit |
| `backend/app/license.py` | LicenseManager: активация, проверка HMAC |
| `backend/app/fingerprint.py` | Сбор CPU/MAC/disk/board для привязки к машине |
| `backend/app/pipeline.py` | Основной пайплайн: Whisper → Claude → FFmpeg |
| `backend/app/workers/standalone_tasks.py` | threading.Thread обёртка для задач |
| `platforms/desktop_windows/src/main/index.ts` | IPC handlers (checkLicense, checkTrial, uploadFile, submitUrl...) |
| `platforms/desktop_windows/src/main/backend.ts` | Запуск backend.exe, поиск порта |
| `renderer/App.tsx` | Главный компонент: фазы, экраны, auth, trial логика |
| `renderer/i18n/ru.ts` | Master i18n (все строки на русском) |
| `renderer/lib/supabaseClient.ts` | Supabase клиент с graceful degrade |
| `renderer/hooks/useAuth.ts` | Auth state из Supabase |
| `renderer/styles/globals.css` | Все CSS стили |
| `tools/keygen.py` | Генератор ключей TRSK-* |
| `supabase/migrations/20260313140631_create_user_licenses.sql` | БД схема user_licenses + RLS |
| `build_all.bat` | Полная пересборка (PyInstaller + installer) |
| `rebuild_installer.bat` | Только Electron сборка + NSIS |

---

## 8. Известные ограничения и gotchas

### OneDrive EEXIST
Файлы проекта на OneDrive. Инструмент `Edit` иногда падает с `EEXIST: file already exists, mkdir`.
**Workaround**: писать в `C:/Users/Admin/AppData/Local/Temp/`, затем `shutil.copy2()` к цели.

### TypeScript TranslationKeys
`export type TranslationKeys = typeof ru` инферирует literal types → en.ts/zh.ts падают.
**Решение**: использовать `DeepString<T>` utility type в `ru.ts`.

### Supabase в Electron
CSP в `index.html` должен разрешать `https://*.supabase.co` и `wss://*.supabase.co` — уже настроено.
Auth storage = `window.localStorage` (не electron-store) — достаточно для MVP.

### PyInstaller + Windows 11
- Антивирус может блокировать `backend.exe` (false positive)
- HKLM запись (TrialInit) требует прав администратора при первом запуске
- На 32-bit Windows AI-фичи (Whisper/PyTorch) недоступны

### Backend порт
Бекенд стартует на случайном свободном порту, Electron читает его через stdout parsing в `backend.ts`.

---

## 9. Текущий статус (2026-03-13)

### ✅ Полностью готово
- FastAPI backend с PyInstaller сборкой
- Пайплайн: upload → Whisper → Claude → FFmpeg → результат
- Trial система (мульти-слойная, anti-bypass)
- Лицензионная система (офлайн HMAC, 3 плана)
- Генератор ключей (`tools/keygen.py`)
- Electron shell (Windows x64 + ia32)
- Universal NSIS installer (`rebuild_installer.bat`)
- React UI: все 3 экрана (Главная / Как работает / Цены)
- Полный i18n: русский / английский / китайский
- Переключение темы: light / dark
- Supabase Auth: login / register / forgot password
- SetupWizard онбординг
- Изоляция всех путей в AppData

### 🔲 Ещё не реализовано / незакрытые вопросы

1. **SQL миграция в Supabase cloud**
   Файл `supabase/migrations/20260313140631_create_user_licenses.sql` написан,
   но **не применён** к проекту `aakxqjpyikhjzkfvwppu`.
   → Открыть Supabase Dashboard → SQL Editor → выполнить.

2. **Привязка лицензии к Supabase аккаунту**
   Таблица `user_licenses` готова, но логики активации ключа через UI нет.
   После логина пользователь должен ввести TRSK-ключ → записать в `user_licenses`.

3. **История задач (Screen)**
   В навигации есть кнопка "История" (`nav.history`), экран не реализован.

4. **ResultGallery**
   Показывает результаты, но нет превью/плеера — только ссылки на файлы.

5. **macOS платформа**
   `platforms/desktop_mac/` существует (scaffold), но не разрабатывалась.

6. **Иконка приложения**
   `build/icon.ico` не создан. В `electron-builder.yml` иконка закомментирована.

7. **Пересборка после Trial enforcement**
   После добавления `record_video()` и `can_process()` в backend — нужна пересборка `backend.exe`.
   Текущий `backend.exe` в release может быть устаревшим.
   → Запустить `build_all.bat`.

8. **Тестирование на чистой машине**
   Не проверяли установку с нуля (первый запуск, загрузка Whisper модели ~461MB).

---

## 10. Следующие приоритеты (в порядке важности)

1. Применить SQL миграцию в Supabase (5 мин, ручное действие)
2. Реализовать активацию лицензионного ключа через UI (SetupWizard + Supabase)
3. Пересборка `backend.exe` с актуальными trial enforcement изменениями
4. Создать иконку приложения (`build/icon.ico`)
5. Реализовать экран Истории (список прошлых обработок)
6. Превью видео в ResultGallery
7. Тестирование на чистой машине (fresh install)
8. macOS платформа

---

## 11. Команды разработчика

```bash
# Dev (browser mode, без Electron)
cd platforms/desktop_windows && npm run dev

# Dev (полный Electron)
cd platforms/desktop_windows && npm run dev

# Typecheck
cd platforms/desktop_windows && npm run typecheck

# Генерация лицензионных ключей
cd tools && python keygen.py

# Сброс trial (для тестирования)
python tools/reset_trial.py

# Полная пересборка релиза
build_all.bat

# Только пересборка Electron installer
rebuild_installer.bat
```

---

## 12. Supabase проект

- **URL**: `https://aakxqjpyikhjzkfvwppu.supabase.co`
- **Dashboard**: `https://supabase.com/dashboard/project/aakxqjpyikhjzkfvwppu`
- **Auth Users**: `/auth/users`
- **SQL Editor**: `/sql`
- **API Settings**: `/settings/api`
- Email confirmation: **отключён** (для тестирования)
