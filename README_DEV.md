# Transkrib SmartCut AI — Developer Guide

## Quick Start

```bat
dev_start.bat   # запускает backend + Electron dev
dev_stop.bat    # останавливает все dev-процессы
```

---

## Что запускается

| Процесс | Порт | Описание |
|---------|------|----------|
| Python FastAPI backend | 8000 | `backend/standalone_server.py` |
| Vite (React renderer) | 5173 | Hot-reload для UI |
| TypeScript watch | — | Компилирует `src/main/*.ts` |
| Electron | — | Загружает `http://localhost:5173` |

---

## Dev Mode (`APP_DEV_MODE=true`)

Установлен в `backend/.env`. Отключает:
- Проверку триального периода (trial gate)
- Проверку лицензии

Frontend тоже определяет dev-режим:
- URL-параметр `?dev=true`
- `localStorage.setItem('transkrib_dev_mode', 'true')`

В dev-режиме `BackendStartup` не показывается — приложение стартует сразу.

---

## Структура проекта

```
Transkrib_SmartCut_AI/
├── backend/                    # FastAPI + Whisper + Claude
│   ├── app/
│   │   ├── routers/            # API endpoints
│   │   ├── services/           # Whisper, FFmpeg, Claude, ...
│   │   └── config.py           # Настройки через env vars
│   ├── standalone_server.py    # Точка входа (dev + PyInstaller)
│   ├── backend.spec            # PyInstaller spec
│   └── .env                    # Локальные ключи (не в git)
│
├── platforms/desktop_windows/  # Electron app
│   ├── src/
│   │   ├── main/               # Electron main process
│   │   │   ├── index.ts        # IPC handlers, window setup
│   │   │   ├── backend.ts      # Запуск backend.exe subprocess
│   │   │   └── preload.ts      # electronAPI bridge
│   │   └── renderer/           # React UI
│   │       ├── components/     # UI компоненты
│   │       ├── i18n/           # ru / en / zh переводы
│   │       ├── services/api.ts # HTTP клиент к backend
│   │       └── styles/         # globals.css
│   ├── electron-builder.yml    # NSIS installer конфиг
│   └── package.json
│
├── tools/
│   ├── keygen.py               # Генератор лицензионных ключей
│   ├── generate_keys.bat       # Запуск keygen
│   └── reset_trial.py          # Сброс триального периода
│
├── build_all.bat               # Полная сборка (PyInstaller + NSIS)
├── rebuild_installer.bat       # Только Electron + NSIS (без backend)
├── dev_start.bat               # Запуск dev-окружения
└── dev_stop.bat                # Остановка dev-окружения
```

---

## Backend — переменные окружения (`backend/.env`)

| Переменная | Пример | Описание |
|------------|--------|----------|
| `APP_ANTHROPIC_API_KEY` | `sk-ant-...` | Claude API key |
| `APP_WHISPER_MODEL` | `tiny` / `small` / `medium` | Модель Whisper |
| `APP_STABILITY_API_KEY` | `sk-...` | Stability AI (preview) |
| `APP_DEV_MODE` | `true` | Отключает trial/license |
| `APP_INTRO_DURATION` | `60` | Обязательные первые N сек |
| `APP_ENDING_DURATION` | `60` | Обязательные последние N сек |

Все переменные с префиксом `APP_`. Файл `.env` не коммитится.

---

## API Endpoints

Swagger UI: **http://127.0.0.1:8000/docs**

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/tasks/upload` | Загрузить видео |
| POST | `/api/tasks/url` | Обработать URL (YouTube и др.) |
| GET | `/api/tasks/{id}` | Статус задачи |
| WS | `/ws/tasks/{id}/progress` | WebSocket прогресс |
| GET | `/api/results/` | Список готовых видео |
| GET | `/api/transcript/{file}` | Сегменты + formatted_text |
| GET | `/api/transcript/{file}/download?format=txt\|srt\|json\|html` | Скачать транскрипт |
| GET | `/api/system/trial` | Статус триала |
| GET | `/api/system/dev/status` | Dev mode статус (только если DEV_MODE=true) |

---

## Полная сборка

```bat
build_all.bat
```

1. PyInstaller → `backend/dist/backend.exe` + `_internal/`
2. `npm run build` (Vite + tsc)
3. electron-builder → 3 NSIS инсталлятора в `platforms/desktop_windows/release/`
4. Версионирование → `Transkrib-Setup-bNNN-YYYY-MM-DD*.exe`

---

## Только Electron (без пересборки backend)

```bat
rebuild_installer.bat
```

Используется когда изменился только UI (не Python-код).

---

## Лицензионные ключи

```bat
tools\generate_keys.bat
```

Генерирует ключи в `Transkrib_Keys/`:
- `plan_basic/` — 50 ключей BASE (10 дней)
- `plan_standard/` — 30 ключей STND (30 дней)
- `plan_pro/` — 15 ключей PREM (365 дней)

Формат: `TRSK-{PLAN}-{XXXX}-{XXXX}-{HMAC8}`

---

## Сброс триального периода (для тестирования)

```bat
python tools\reset_trial.py
```

Удаляет `storage/trial.dat` и записи в реестре HKCU/HKLM.

---

## Хранилище данных

Всё изолировано в `AppData\Roaming\Transkrib\storage\`:

```
storage/
├── uploads/          # Загруженные видео
├── processing/       # FFmpeg + промежуточные файлы
├── results/          # Готовые highlight-видео + транскрипты
│   ├── *.mp4
│   ├── *_segments.json
│   └── *_formatted.txt   # Кэш Claude-форматирования
├── whisper_models/   # .pt файлы (~461MB для small)
├── logs/             # backend.log, backend_dev.log
└── .license/         # license.key
```

---

## Известные особенности

- **OneDrive**: Edit-tool Claude Code иногда падает с EEXIST — workaround через Python + shutil.copy
- **CRLF**: Python-файлы должны иметь LF. При редактировании в Windows проверяй line endings
- **PyInstaller `_internal/`**: все Python-зависимости изолированы, конфликтов DLL нет
- **Electron titlebar**: `-webkit-app-region: drag` на `.title-bar`, `no-drag` на все интерактивные элементы
