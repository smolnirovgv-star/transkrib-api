# Transkrib — Зафиксированные баги и решения

## ✅ Эпохальные рабочие сборки (safe rollback points)

| Дата | Tag | Коммит | Что работает |
|---|---|---|---|
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
