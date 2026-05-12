# Strategic Decisions

Документ для долгосрочных стратегических решений и инсайтов от внешних консультаций. Дополняет 05-roadmap.md (что делаем) перечнем что СОЗНАТЕЛЬНО НЕ делаем и почему.

## 2026-05-12 — Ответ внешнего аналитика, ключевые решения

### Архитектура ingestion

**Принято:**
- yt-dlp переводится в secondary fallback (не primary)
- Целевая архитектура: Ingestion Router pattern с 4 уровнями (cobalt → residential yt-dlp → telegram_direct → external API)
- Recommended residential proxy: **IPRoyal Residential** (~$10-15/мес, low-tier план достаточно)
- Главный принцип: **resilience > clever hacks**

**Отвергнуто:**
- ❌ PO Token путь (Node.js сайдкар, ротация токенов каждые 12ч, complexity hell для solo founder)
- ❌ Browser impersonation / TLS spoofing — не лечит ASN, добавляет maintenance hell
- ❌ Anti-detection stack (rotating sessions, custom fingerprinting) — YouTube выиграет escalation war
- ❌ Любые попытки найти "бесплатный bypass YouTube ASN" — это architectural reality 2026, бесплатно невозможно

**Cookies infrastructure: diminishing returns trap.** Long-lived server-side YouTube cookies — dead architecture. Не инвестировать.

### Bug #19 closure (когда придёт время активации)

**Готовый промт Cursor для активации residential proxy через IPRoyal:**

```
Контекст: куплен IPRoyal Residential proxy. Нужно переключить yt-dlp с Webshare datacenter на IPRoyal residential. Этот шаг закрывает Bug #19.

Изменения:
1) Railway transkrib-api ENV: добавить IPROYAL_PROXY="http://USER:PASS@geo.iproyal.com:PORT" (значение из секретов).
2) backend/app/services/health_monitor.py — функция _get_proxy_url_for_health(): приоритет IPROYAL_PROXY → YOUTUBE_PROXY → WEBSHARE_PROXY (fallback в порядке убывания качества).
3) backend/app/routers/bot_tasks.py:1053 — заменить захардкоженный default WEBSHARE_PROXY на os.environ.get("IPROYAL_PROXY") or os.environ.get("WEBSHARE_PROXY") без хардкода. Это закрывает Bug #5 параллельно.
4) [WATCHDOG_YTDLP_PRE] лог: добавить поле proxy_provider (iproyal / webshare / none) для визуальной верификации в логах.

НЕ менять player_client (остаётся ['android', 'web']), не менять cookies логику, не менять других методов скачивания.

После деплоя watchdog покажет результат в следующем цикле — ожидаемое: success=True для yt-dlp.
```

### Продуктовые решения

**Принято:**
- AI co-pilot editor (НЕ fully autonomous) — AI готовит rough cuts, человек финализирует. Это реалистично для 2026.
- Pricing direction: freemium + paid acceleration (free с watermark/queue, paid: priority/HD/no watermark/AI editing/batch)
- Acquisition channel #1: Reels/Shorts demo content ("Из 2-часового подкаста → 10 Shorts за 30 секунд")
- Acquisition channel #2: Build in Public (показывать failures, architecture, AI workflows)
- Acquisition channel #3: Telegram creator channels (СНГ creator economy)
- Micro-influencers: revenue-share/affiliate, не платные интеграции upfront

**Отвергнуто:**
- ❌ SEO как первый канал — слишком долго, expensive in time
- ❌ Дифференциация через цену — trap. Лучше через качество результата и creator workflow UX
- ❌ Fully autonomous AI editor — narrative pacing, emotional/comedic timing AI ещё не умеет
- ❌ Pay-per-use модель — плохо для retention

### Глобальная экспансия

**Принято:** English-first global creator market как первый шаг.

**Отвергнуто:**
- ❌ Китай — payments/ICP complexity/regulations, нереально для solo founder
- ❌ Индия как первый рынок — низкий ARPU, support load
- ❌ Локализация под отдельные страны до English-first валидации

**Pre-validation для глобализации:** Product Hunt, Reddit, YouTube, TikTok с английским продуктом. Локализация — потом.

### Hiring и operational load

**Founder overload critical risk** — операционная нагрузка приближается к threshold.

**Первый помощник:** support/operations person (НЕ DevOps первым). Освобождает founder cognition.

**Триггер найма:** если operations съедают >35% времени или тормозят roadmap.

**Что автоматизировать ПРЯМО СЕЙЧАС:**
1. Monitoring (healthchecks, ingestion failures, alerting) — частично есть в watchdog
2. CI/CD с rollback и auto-health validation
3. AI support agent / FAQ / ticket triage
4. Billing monitoring
5. **Provider abstraction layer** — критически важно. Не завязываться на одного ingestion / AI / proxy провайдера.

### Niche wedge для дифференциации

Не пытаться "сделать OpusClip". Найти creator niche wedge:
- podcasters
- education creators
- Russian-speaking creators (текущий органический actant)
- Telegram creators (специфика СНГ)
- YouTube educators

### Legal/platform risk (blind spot)

Проект structurally depends on violating YouTube platform intent. Строить архитектуру как hostile-environment system: providers WILL break, YouTube WILL escalate, APIs WILL change, costs WILL rise.

## Priority Matrix (по аналитику)

| Приоритет | Проблема | Статус |
|---|---|---|
| P0 | YouTube delivery reliability | Bug #19 closure через residential — pending decision |
| P1 | Single point of failure (cobalt) | Ingestion Router в roadmap |
| P1 | Founder overload | Provider abstraction + support hire (когда >35% времени на ops) |
| P2 | Distribution & acquisition | Reels/Shorts/Build in Public — не начато |
| P3 | AI editing automation | v1.2+ co-pilot, не autonomous |
| P4 | Global expansion | English-first; не локализация |
