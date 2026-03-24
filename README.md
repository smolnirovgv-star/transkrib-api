# Transkrib — Video Transcription & Highlights Tool

Кросс-платформенное приложение для обработки видео: транскрибация через Whisper, анализ ключевых моментов через Claude API, автоматическая сборка highlights.

## Архитектура

```
app/
├── backend/          Python FastAPI + Celery + Redis
├── platforms/
│   ├── browser/      React SPA (glassmorphism)
│   ├── desktop_windows/  Electron (Fluent Design)
│   ├── desktop_mac/      Electron (Apple HIG)
│   └── mobile/           React Native (Expo)
├── docker-compose.yml
└── package.json
```

## Быстрый старт (Docker)

```bash
# 1. Скопируйте .env
cp .env.example .env
# Отредактируйте .env — укажите ANTHROPIC_API_KEY

# 2. Запустите всё одной командой
docker-compose up --build

# 3. Откройте в браузере
# http://localhost:3000     — веб-интерфейс
# http://localhost:8000/docs — Swagger API документация
```

## Локальная разработка

### Требования
- Python 3.11+
- Node.js 20+
- Redis
- FFmpeg
- Anthropic API ключ

### Backend

```bash
cd backend
pip install -r requirements.txt

# Запустить API сервер
uvicorn app.main:app --reload --port 8000

# В отдельном терминале — Celery worker
celery -A app.workers.celery_app worker --loglevel=info --concurrency=1
```

### Browser (веб-версия)

```bash
cd platforms/browser
npm install
npm run dev
# Откройте http://localhost:5173
```

### Desktop Windows

```bash
cd platforms/desktop_windows
npm install
npm run dev          # Режим разработки
npm run build:windows  # Сборка .exe установщика (NSIS)
```

### Desktop Mac

```bash
cd platforms/desktop_mac
npm install
npm run dev          # Режим разработки
npm run build:mac    # Сборка .dmg установщика
```

### Mobile (iOS / Android)

```bash
cd platforms/mobile
npm install
npx expo start       # Запуск Expo dev server
# Сканируйте QR-код в Expo Go
```

## API Endpoints

| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/api/tasks/upload` | Загрузить видеофайл |
| POST | `/api/tasks/url` | Отправить URL (YouTube, VK) |
| GET | `/api/tasks/{id}` | Статус задачи |
| GET | `/api/tasks/` | Список задач |
| WS | `/ws/tasks/{id}/progress` | Прогресс в реальном времени |
| GET | `/api/results/` | Список результатов |
| GET | `/api/results/{name}/download` | Скачать результат |
| GET | `/api/results/{name}/stream` | Стриминг видео |
| GET | `/api/system/health` | Health check |
| GET | `/api/system/info` | Информация о системе |

## Пайплайн обработки

1. **Конвертация** — FFmpeg конвертирует в MP4 H.264+AAC
2. **Транскрибация** — Whisper (модель small) с таймкодами `[HH:MM:SS - HH:MM:SS]`
3. **Анализ** — Claude API выбирает ключевые смысловые эпизоды (10-15% видео)
4. **Сборка** — FFmpeg вырезает фрагменты и склеивает с плавными переходами (0.5с crossfade)
5. **Результат** — `NNN_YYYY-MM-DD_название.mp4` в папке results

## Сборка для всех платформ

```bash
npm run build:windows   # .exe установщик (NSIS)
npm run build:mac       # .dmg установщик
npm run build:browser   # Статичная веб-версия
npm run build:mobile    # Expo build для iOS/Android
```

## Переменные окружения (.env)

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `APP_ANTHROPIC_API_KEY` | Ключ Anthropic API | — |
| `APP_WHISPER_MODEL` | Модель Whisper | `small` |
| `APP_CLAUDE_MODEL` | Модель Claude | `claude-sonnet-4-5-20250929` |
| `APP_CELERY_BROKER_URL` | Redis URL | `redis://localhost:6379/0` |
| `APP_STORAGE_DIR` | Директория хранения | `./storage` |

## Мультиязычность

Поддерживаемые языки интерфейса:
- 🇷🇺 Русский (по умолчанию)
- 🇬🇧 English
- 🇨🇳 中文

Переключатель языка доступен в header/настройках каждой платформы.

## Технологии

- **Backend:** Python, FastAPI, Celery, Redis, Whisper, Anthropic Claude API
- **Browser:** React, Vite, TypeScript, Framer Motion
- **Desktop:** Electron, React, Vite, TypeScript
- **Mobile:** React Native, Expo, TypeScript
- **Инфраструктура:** Docker, nginx, FFmpeg, yt-dlp
