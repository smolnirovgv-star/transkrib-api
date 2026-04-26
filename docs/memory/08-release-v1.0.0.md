# Release v1.0.0 — 26.04.2026

## Состояние на момент релиза
HEAD transkrib-api: 9271ff3
HEAD transkrib-bot: 695b73a (тестировано 25.04, не менялось)
HEAD transkrib-admin-bot: 2176af6 (watchdog добавлен)
Stable tag: stable-feat-pack-2026-04-25 (предыдущий якорь, перед релизом)
Release tag: v1.0.0 (создан вместе с этим документом)

## Что вошло в v1.0.0 (по сравнению с stable-feat-pack-2026-04-25)
- transkrib-api: feat(metrics) 92536ff + docs 9271ff3 (запись task_metrics)
- transkrib-admin-bot: feat(watchdog) 2176af6 (потребление метрик)
- Supabase task_metrics таблица создана вручную через Dashboard

## Production-инфраструктура (зафиксировано)

### Railway services
- transkrib-api: eb3eb8ff-155e-45c2-a1d1-7aa2ff5d2f19, region us-west2, URL https://transkrib-api-production.up.railway.app
- transkrib-bot: 158d6319-ff68-462f-b4a6-535e1c853ffa
- transkrib-admin-bot: отдельный сервис Railway
- cobalt: 7b831c27

### Env vars (имена, без значений)
transkrib-api: ANTHROPIC_API_KEY, GROQ_API_KEY, SUPABASE_URL, SUPABASE_KEY, YOUTUBE_COOKIES_B64, WEBSHARE_PROXY_URL, RAPIDAPI_KEY, SUPADATA_API_KEY, COBALT_API_URL
transkrib-bot: BOT_TOKEN, API_BASE_URL, SUPABASE_URL, SUPABASE_KEY, YOKASSA_SHOP_ID, YOKASSA_SECRET_KEY, ADMIN_ID
transkrib-admin-bot: BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY, ADMIN_ID

### Supabase tables
- bot_users (id, telegram_id, created_at, ...)
- invite_codes (code, used_by, used_at, ...)
- task_metrics (task_id PK, created_at, final_status, cut_status, download_method, formatter_status, processing_time_sec)

## Production-тесты пройденные
- Test 1: PCZywVQ9ceQ + 5мин + Транскрипция+нарезка → PASS (~2 мин)
- Test 2: PCZywVQ9ceQ + 5мин + Нарезка+SRT → PASS после retry (download transient)
- Test 3: dQw4w9WgXcQ Rick Astley + Транскрипция → PASS (copyright fallback сработал)
- Watchdog end-to-end: /metrics показал 1 task с правильной классификацией

## Открытые вопросы (не блокеры)
- Transcript truncation ~3500 chars (нужен split на 4096-char Telegram messages)
- VK timeout >10 min — root cause не диагностирован
- Cut button asks for URL again — state lost in ConversationHandler
- helpers _get_cookie_file/_prepare_ytdlp_cookies — duplication tech debt

## Roadmap (priorities post-v1.0.0)
1. Balances monitoring extension в admin-bot (Anthropic, RapidAPI, Supadata, ЮKassa, Railway). Пороги: красный <5%, жёлтый <20%, зелёный >=20%
2. yt-dlp audio+480p only (5-10x speedup)
3. Pause/filler word removal
4. Video summary
5. Frontend локализации India/China/Korea/Brazil
6. Дополнительные uniform-cut алгоритмы B/C для тестирования
