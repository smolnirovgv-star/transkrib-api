# Transkrib SmartCut AI — v1.0.0 Project Summary

## Что это
AI-powered video transcription and smart-cut service. Принимает YouTube/Rutube ссылку → транскрибирует → форматирует → нарезает на смысловые блоки. Multi-language: автоопределение языка (Whisper Large v3 Turbo), форматирование на русском/английском (Claude Sonnet 4). Поддержка любых стран и языков пользователя.

## Архитектура
- transkrib-api (FastAPI, Railway): backend pipeline
- transkrib-bot (python-telegram-bot, Railway): пользовательский бот @transkrib_smartcut_bot
- transkrib-admin-bot (PTB, Railway): админ-бот @TranskribAdmin_Bot с watchdog
- Supabase (Postgres): bot_users, invite_codes, task_metrics
- ЮKassa: платежи (ShopID 1302226)
- Cobalt + yt-dlp + RapidAPI + Supadata: download fallback chain

## Возможности v1.0.0
- 4 формата выдачи: транскрипт, транскрипт+нарезка, SRT субтитры, нарезка+SRT, Markdown
- 6 длительностей нарезки: 5/10/15/20/30 мин или без сокращения
- 3 режима языка: Auto/RU/EN
- Resilient pipeline: cookies для YouTube anti-bot, fallback на Supadata/RapidAPI/Cobalt
- Smart-cut с graceful degradation: при невалидных Claude-segments → uniform fallback
- Copyright-protected content: graceful degradation на сырой транскрипт
- Admin watchdog: edge-trigger алерты при <90% метрик
- Pricing: Trial 0₽/30мин, Базовый 450₽, Стандарт 1700₽, Про 8900₽

## Технологический стек
Backend: FastAPI, Python 3.11
LLM: Claude Sonnet 4, Whisper Large v3 Turbo (Groq)
Инфраструктура: Railway (Docker), Supabase, Cloudflare Tunnel
Boilerplate: yt-dlp, ffmpeg (H.264+AAC unified), python-telegram-bot v21

## Метрики качества (production)
- 3/3 manual test scenarios PASS (Транскрипция+нарезка, Нарезка+SRT, Copyright fallback)
- Pipeline avg ~33 секунды для 3-минутного видео
- Watchdog покрывает 5 метрик: cut/download/uniform_fallback/copyright_fallback/overall

## Multi-language support
- Whisper auto-detect: 99+ языков транскрибируется без ручного выбора
- Claude formatter: понимает любой исходный язык, форматирует на запрошенном
- UI бота: русский, готов к локализации (структурно тексты вынесены)

## Roadmap (post-v1.0.0)
См. docs/memory/05-roadmap.md. Главное направление: расширение balances monitoring (admin-bot), мобильное приложение (десктоп уже есть в transkrib desktop), глобальные frontend-локализации (India/China/Korea/Brazil), добавление uniform-cut алгоритмов B/C для тестирования.

## Контакты и ссылки
- Бот: https://t.me/transkrib_smartcut_bot
- Сайт: https://transkrib.su
- Поддержка: schwed.2000@mail.ru
- Дата релиза: 26.04.2026
