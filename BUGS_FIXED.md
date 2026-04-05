# Transkrib — Зафиксированные баги и решения

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
