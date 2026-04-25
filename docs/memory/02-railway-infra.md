# Railway инфраструктура

_Обновлено: 2026-04-25_

## Навигация

- Dashboard: https://railway.com/dashboard
- Проект gallant-healing (c8e80613): transkrib-api + transkrib-bot + cobalt
- Variables URL паттерн: railway.com/project/{projectId}/service/{serviceId}/variables
- GraphQL API: backboard.railway.com/graphql/v2 (использовать credentials:include)

## transkrib-api

**BUILDER**: DOCKERFILE (НЕ NIXPACKS — package.json в корне ломает авто-детекцию).
**Dockerfile**: backend/Dockerfile, context = корень репо (COPY backend/ . и COPY backend/requirements.railway.txt).
**startCommand**: `sh -c 'uvicorn main_railway:app --host 0.0.0.0 --port $PORT'` — sh -c обязательно для интерполяции $PORT.
**healthcheckPath**: /health, timeout 120s.

**Service Variables (9):**
- ANTHROPIC_API_KEY
- APP_ANTHROPIC_API_KEY
- GROQ_API_KEY
- RAPIDAPI_KEY
- SUPADATA_API_KEY
- WEBSHARE_PROXY
- YOOKASSA_SECRET_KEY
- YOOKASSA_SHOP_ID
- YOUTUBE_COOKIES_B64

## transkrib-bot

**Service Variables (6):**
- ADMIN_ID = 5052641158
- ANTHROPIC_API_KEY
- SUPABASE_KEY
- SUPABASE_URL
- TELEGRAM_BOT_TOKEN
- TRANSKRIB_API_URL = https://transkrib-api-production.up.railway.app

## История проблем с билдами (из ретроспективы)

1. Тяжёлые pip-пакеты в requirements → перенесли в requirements.railway.txt
2. Нужны nixpkgs python311 + ffmpeg → добавили
3. nixpacks.toml ломал → удалили, ffmpeg-python в pip
4. uvicorn not in PATH → перешли на python -m uvicorn
5. python not found → финал: python3 -m uvicorn (для Nixpacks-вариантов; для Dockerfile см. startCommand выше)

## Render (резерв)

- transkrib-api на Render: srv-d6voti95pdvs738pmc6g — оставлен как backup, **НЕ удалять**.
- Известный баг: Google Translate в Chrome ломает React-формы Render Dashboard (env vars не сохраняются). Решение: "Show original" в панели Translate перед редактированием.
