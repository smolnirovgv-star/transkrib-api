# Архитектура проекта

_Обновлено: 2026-04-25_

## Компоненты

**transkrib-api** (FastAPI, Python) — главный backend.
- GitHub: smolnirovgv-star/transkrib-api
- Развёрнут: Railway (us-west2), сервис eb3eb8ff-155e-45c2-a1d1-7aa2ff5d2f19
- URL: https://transkrib-api-production.up.railway.app
- Резерв: Render srv-d6voti95pdvs738pmc6g (НЕ удалять)

**transkrib-bot** (python-telegram-bot) — Telegram-бот.
- GitHub: smolnirovgv-star/transkrib-bot
- Развёрнут: Railway, сервис 158d6319-ff68-462f-b4a6-535e1c853ffa
- Username prod: @transkrib_smartcut_bot
- Username test: @transkrib_test_bot

**TranskribAdmin_Bot** (отдельный) — мониторинг, статус, watchdog.
- watchdog: периодически читает task_metrics, алертит в ADMIN_ID при падении метрик ниже 90% (edge-trigger); данные из Supabase.task_metrics
- Username: @TranskribAdmin_Bot
- ADMIN_ID: 5052641158

**Cobalt** (видео-downloader) — Railway, сервис 7b831c27.

**Transkrib Desktop** (Electron + Python) — десктопное приложение, отдельный продукт.
- Сайт: https://transkrib.su (Tilda, project ID 11160975)
- v1.0.1 — рабочая, опубликована
- v1.1.0+ — в разработке

## Внешние зависимости

- Groq Whisper (whisper-large-v3-turbo) — транскрипция
- Anthropic Claude (claude-sonnet-4-20250514) — форматирование, сегментация
- Supadata — fallback transcript YouTube
- Webshare proxy — обход YouTube антибота для pytubefix
- RapidAPI YouTube Media Downloader (DataFanatic) — fallback скачивания
- Supabase aakxqjpyikhjzkfvwppu — БД (общая для prod и test, таблицы test_*)
- ЮKassa ShopID 1302226 — платежи

## Ветки

- main — production
- test — экспериментальная (минутные тарифы Trial/Базовый/Стандарт/Про, чанкинг)
- bot-test — будущая, для следующего цикла экспериментов (пока не создана)

## Стабильные теги

См. 07-decisions-log.md для актуального списка epoch/* и stable-* тегов.
