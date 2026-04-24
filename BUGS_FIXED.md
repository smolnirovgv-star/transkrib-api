# Transkrib — Зафиксированные баги и решения

## ✅ Эпохальные рабочие сборки (safe rollback points)

| Дата | Tag | Коммит | Что работает |
|---|---|---|---|
| 2026-04-22 12:00 | epoch/production-2026-04-22 | cb0d136 | 🏆🏆 100% PRODUCTION: all 4 formats + timer UX + payments |
| 2026-04-22 | epoch/full-pipeline-with-payments-2026-04-22 | b21ae46b50a3de160887f81e19367b36e241090a | 🏆 PRODUCTION: YouTube+Groq+Claude+нарезка+ЮKassa |
| 2026-04-21 20:59 | epoch/full-pipeline-working-2026-04-21 | 6287a12d0985325f94d833b9ffb8713b991486cd | 🏆 ВСЯ ЦЕПОЧКА: YouTube+Groq+Claude формат+нарезка видео |
| 2026-04-21 | epoch/youtube-groq-working-2026-04-21 | 383e9a0a84fe1e7088e5d3e4cca516164a544aea | YouTube+Groq полная цепочка |
| 2026-04-20 | test-2026-04-21 | 9e0feef | Rollback к простому pytubefix |

Откат: git checkout <tag> → Railway redeploy (2 минуты).


## КРИТИЧНО — выполнять при каждой сборке

### 1. GitHub Release уходит в Draft
**Когда:** каждый раз при пересоздании тега v1.0.1
**Решение:** после любого `git tag v1.0.1` обязательно выполнить:
gh release edit v1.0.1 --draft=false --latest
**Уже в:** rebuild_windows.bat (шаг 5/5)

### 2. Windows exe маленький (из CI вместо локального)
**Когда:** CI перезаписывал Windows файлы своими маленькими (75MB вместо 372MB)
**Решение:** в .github/workflows/build.yml убран build-windows из publish-release
**Уже исправлено:** коммит b0562da

### 3. Whisper зависает при каждом запуске
**Когда:** HF_HUB_OFFLINE=1 устанавливался до проверки кэша
**Решение:** убрать весь HF_HUB_OFFLINE код — faster-whisper сам кэширует через download_root
**Уже исправлено:** в transcription_service.py

### 4. Ошибка 401 invalid x-api-key при обработке видео
**Когда:** backend/.env содержит старый/отозванный ключ Anthropic
**Решение:** при создании нового ключа обновлять ОБА места:
- backend/.env → APP_ANTHROPIC_API_KEY=новый_ключ
- Render Dashboard → APP_ANTHROPIC_API_KEY=новый_ключ
- Затем запустить rebuild_windows.bat

### 5. silero_vad_v6.onnx не найден
**Когда:** файл не был включён в PyInstaller bundle
**Решение:** в backend/transkrib.spec в секции datas должно быть:
faster_whisper_datas = [
('C:/Users/Admin/AppData/Local/Programs/Python/Python311/Lib/site-packages/faster_whisper/assets',
'faster_whisper/assets'),
]
**Уже исправлено:** в transkrib.spec

### 6. SetupWizard блокирует запуск после триала
**Когда:** localStorage не содержал trialStarted
**Решение:** в App.tsx условие: `!trialStarted` добавлено к проверке
**Уже исправлено:** коммит в App.tsx (оба платформы)

### 7. Удалённое видео возвращается
**Когда:** polling каждые 10 сек перезаписывал весь список
**Решение:** useRef<Set<string>> для хранения удалённых файлов
**Уже исправлено:** ResultGallery.tsx

## Чеклист перед выпуском новой версии
- [ ] rebuild_windows.bat выполнен успешно
- [ ] backend/.env и Render APP_ANTHROPIC_API_KEY одинаковы
- [ ] gh release edit v1.0.1 --draft=false --latest выполнен
- [ ] Проверить transkrib.spec — silero_vad_v6.onnx в datas
- [ ] Протестировать: установка → запуск → обработка видео

### 8. Кнопка "Сбросить" пароль не отправляет письмо восстановления
**Когда:** Site URL в Supabase был установлен на /parol-smena и при попытке сброса пользователь не получал письмо восстановления.
**Решение:** Site URL в Supabase Dashboard = https://transkrib.su
Для корректной работы восстановления используется redirectTo в коде:
```
supabase.auth.resetPasswordForEmail(email, {
  redirectTo: 'https://transkrib.su/parol-smena'
})
```
**НЕЛЬЗЯ менять Site URL в Supabase на конкретную страницу восстановления!**

### 9. Кнопка "Купить" не работала
**Причина:** fetch из Electron renderer process блокируется.
**Решение:** перенести запрос в main process через IPC:
- preload: createPayment через ipcRenderer.invoke
- main: ipcMain.handle через electron.net
- renderer: window.electronAPI.createPayment(...)
### 10. Кнопка "Купить" — YOOKASSA_SECRET_KEY должен быть боевым
**Когда:** при обновлении env vars на Render случайно вставляется тестовый ключ test_...
**Решение:** YOOKASSA_SECRET_KEY на Render ВСЕГДА должен быть боевым ключом live_...ZJp8
из файла "ключи для работы/secret_key ю-касса.txt"
**Проверка:** curl /api/payments/create → если 401 invalid_credentials → ключ тестовый!
**Никогда:** не вставлять test_... ключ в боевой Render


### 11. CUT-регрессия: int path + ffmpeg args parsing (24.04.2026)
**Когда:** feat(resize) 23.04.2026 — после переделки chunks и /tmp-файлов
**Bug #1:** `[CUT] exception: expected str, bytes or os.PathLike object, not int`
**Причина:** Claude иногда возвращает start_time/end_time как `int` (секунды), а не строку "HH:MM:SS".
`subprocess.run` с `list` падает если элемент `int`.
**Исправление:** `start = str(chunk.get("start_time") or "00:00:00")`

**Bug #2:** `Error parsing options for output file /tmp/..._seg0.mp4`
**Причина:** `chunk.get("start_time", default)` возвращает `None` если ключ существует но значение None.
ffmpeg получает пустой/None аргумент для -ss/-to.
**Исправление:** то же — `or "00:00:00"` перехватывает оба случая (None и пустая строка).

**Дополнительно:**
- `logger.exception` вместо `logger.error` → полный traceback в Railway logs
- ffmpeg cmd логируется перед каждым subprocess.run
- `tasks_store["cut_error"]` + уведомление пользователя в Telegram если нарезка упала


### 12. CUT fmt_cut_srt: SRT timestamp comma→dot (24.04.2026)
**Логи:** `Invalid duration for option ss: 00:02:54,264`
**Причина:** Groq Whisper возвращает SRT с запятой как разделителем миллисекунд ("HH:MM:SS,mmm").
Claude читает этот SRT и возвращает те же таймкоды в chunks.
ffmpeg ожидает точку ("HH:MM:SS.mmm") — с запятой падает "Invalid duration".
**Исправление:** `.replace(",", ".")` на start/end перед ffmpeg cmd.
Плюс assertion guard: `re.search(r'\d,\d', arg)` перед subprocess.run.
**Затронутые форматы:** только `fmt_cut_srt` (Нарезка + SRT).

## v1.2.0 Global -- Изменения

### Новые функции:
1. Stripe платежи для международных пользователей
   - POST /api/stripe/create -- Checkout Session
   - POST /api/stripe/webhook -- активация лицензии
   - Цены: BASE $5 / STANDARD $19 / PRO $99
   - Frontend: план с суффиксом _global -> Stripe

2. Контекстное меню правой кнопки мыши
   - Вырезать / Копировать / Вставить / Выделить все
   - Работает во всех input полях

3. Светлая тема -- исправлена контрастность
   - Кабинет пользователя: тёмный текст на светлом фоне

### Для деплоя v1.2.0 нужно добавить в Render:
- STRIPE_SECRET_KEY=sk_live_...
- STRIPE_WEBHOOK_SECRET=whsec_...

### Культурная локализация v1.2.0 Global
1. 7 языков: ru/en/hi/ko/zh/ja/pt
2. Каждый язык -- уникальная цветовая тема
3. Автоматическая смена шрифта (Noto Sans для азиатских языков)
4. Приветствие на родном языке (toast 2 сек)
5. Эмодзи по культуре страны
6. lang атрибут для правильного рендера
