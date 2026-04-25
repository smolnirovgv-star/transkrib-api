# Правила работы с Cursor / Claude Code

_Обновлено: 2026-04-25_

Эти правила соблюдать в КАЖДОМ промте. Они защищают от регрессий и ускоряют итерации.

## Обязательные

1. **"Менять ТОЛЬКО указанные файлы, остальное НЕ ТРОГАТЬ"** — указывать в каждом промте.
2. **"Прочитай docs/memory/04-known-bugs.md и docs/memory/03-cursor-rules.md перед работой"** — перед любой правкой кода.
3. **Не добавлять лишние pip/npm-зависимости** — если зависимость нужна, явно обосновать в промте.
4. **3-минутное правило**: если Cursor не отвечает 3 минуты — assume error, перезапустить.
5. **Перезапуск Cursor после правок** — упоминать в конце промта.
6. **Push в main всегда явно** — Cursor должен явно сказать hash коммита и подтвердить успешный push.

## Плагины и MCP

Когда нужен плагин/MCP — Claude сразу прописывает установку/удаление в промт без отдельного разрешения у Геннадия.

## Известные грабли окружения

- **GitHub web editor ненадёжен для файлов > 10 KB** — использовать локальный clone + git push с временным токеном.
- **Google Translate в Chrome ломает React-формы Render Dashboard** — отключать ("Show original") перед редактированием env vars на Render.
- **Локальная папка с ключами**: `C:\Users\Admin\OneDrive\Desktop\Cursor\Transkrib_SmartCut_AI\ключи для работы\` — скрытая, в .gitignore. Никогда не коммитить.

## Структура коммит-сообщений

`<тип>(<область>): <короткое описание>`

Типы: fix, feat, docs, refactor, test, chore.
Области: cut, download, ui, payments, cookies, api, bot.

Примеры:
- `fix(cut): SRT timestamp comma→dot conversion for ffmpeg -ss`
- `feat(cut): add uniform-cut fallback when Claude-selection invalid`
- `docs: add project memory base for cross-session context`

## Tags / эпохи

После каждой стабилизации — аннотированный тег `stable-intermediate-YYYY-MM-DD` или `epoch/<feature>-YYYY-MM-DD`. Якорь для безопасного отката.

Откат:
```bash
git reset --hard stable-intermediate-2026-04-25
git push --force-with-lease origin main
```
