# Telegram bot — флоу

_Обновлено: 2026-04-25_

## Сценарий пользователя

1. Пользователь отправляет URL (YouTube / VK / Rutube)
2. Бот: "До скольки минут сократить видео?" → кнопки [5 / 10 / 15 / 20 / 30 мин / Без сокращения]
3. Бот: "Что создать?" → кнопки [Только транскрипция / Транскрипция + нарезка / SRT субтитры / Нарезка + SRT / Markdown (.md)]
4. Бот: "Язык транскрипции?" → кнопки [Авто / Русский / English]
5. transkrib-api: скачивание (Webshare + pytubefix → yt-dlp → cobalt → rapidapi → Supadata)
6. Транскрипция через Groq Whisper (whisper-large-v3-turbo)
7. Claude: формирование сегментов для нарезки (если запрошено)
8. ffmpeg: cut + concat
9. Бот: отправка результата в Telegram

## Форматы вывода

| Формат | Что отдаём |
|---|---|
| Только транскрипция | Текст (HTML+эмодзи в Telegram) |
| Транскрипция + нарезка | Текст + видеофайл MP4 |
| SRT субтитры | Файл .srt |
| Нарезка + SRT | Файл .srt + видеофайл MP4 |
| Markdown (.md) | Файл .md |

## Cut-pipeline и uniform-cut fallback (с 2026-04-25, коммит e675f13)

**Триггер uniform-cut**: Claude-selection невалиден если:
- chunks отсутствуют или len(chunks) < 2
- любой start < 0
- любой end > duration
- любой start >= end

**Алгоритм uniform-cut (вариант A — текущий)**: N равных кусков по cut_min_val минут с начала видео, последний усечённый.
Пример: видео 12 мин, cut_min_val=5 → [(0, 300), (300, 600), (600, 720)] — 3 куска по 5/5/2 мин.

**Имплементация**: bot_tasks.py
- `_is_valid_chunks(chunks, duration)` — парсит "HH:MM:SS" → секунды, проверяет 4 условия невалидности
- `_fmt_ts(s)` — конвертирует секунды в "HH:MM:SS" (формат совместим с cut_video_with_ffmpeg)
- `generate_uniform_chunks(duration, cut_min_val)` — генерирует N равных кусков
- Триггер: ~строка 1592, после `chunks = chunk_result.get("chunks", [])`

**Альтернативные алгоритмы (для возможной замены при негативном фидбэке)**:
- B: 2 куска по cut_min_val из центра видео (середина = информативное)
- C: 1 кусок cut_min_val с начала

**UX**: молча. БЕЗ caption-пометки. БЕЗ уведомления пользователя. Финальное видео идентично визуально успешной Claude-нарезке.

**Логирование**: `[CUT] {task_id}: uniform-cut fallback triggered, chunks_received=N, duration=X` — для будущего подсчёта частоты срабатывания.

## Тестовые видео

- PCZywVQ9ceQ (3 мин, образовательное "Как очистить историю Яндекс") — non-copyright, проходит все форматы
- dQw4w9WgXcQ (Rick Astley) — copyright, форматтер отказывает (тест copyright-fallback)

## Платежи

ЮKassa ShopID 1302226, одобрена. См. 05-roadmap.md тарифы.
