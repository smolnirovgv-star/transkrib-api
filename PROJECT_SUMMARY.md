# Transkrib Telegram Stack v1.0.0

Production AI-powered video transcription and smart-cutting service for Telegram users. Released 26.04.2026.

---

## Scope of v1.0.0-telegram

This release covers three repositories that together form the Telegram product:
- **transkrib-api** — backend processing pipeline (FastAPI on Railway)
- **transkrib-bot** — Telegram user-facing bot (python-telegram-bot)
- **transkrib-admin-bot** — operations watchdog and admin tools

**Source support:** YouTube only. Multi-source (VK, Rutube, direct MP3/MP4) planned for v1.1.0.

**Languages:** Russian and English interface; transcription via Whisper supports 99 languages auto-detect.

**Related products** (independent codebases, separately versioned):
- Transkrib Desktop v1.0.1 (Windows app, https://transkrib.su) — released 31.03.2026
- DOM STROY / domkarkas96.ru (construction business)
- Shkola Plus-Minus / schcolaplusminus.ru (education)

---

## Architecture

### Pipeline flow
1. User sends YouTube URL to @transkrib_smartcut_bot
2. Bot collects parameters: cut duration (5/10/15/20/30 min or no cut), output format (transcript-only / transcript+cut / SRT / cut+SRT / Markdown), language (auto/RU/EN)
3. Bot calls transkrib-api (Railway US-West2)
4. transkrib-api: yt-dlp -> Supadata fallback -> RapidAPI fallback -> Cobalt fallback (download)
5. Groq Whisper-large-v3-turbo (transcription)
6. Claude Sonnet 4 (formatting, with copyright detect-and-fallback)
7. ffmpeg (video cutting with uniform-fallback when Claude segments invalid)
8. Result delivered back to user

### Key fault-tolerance mechanisms (all introduced in 25.04.2026 stabilization sprint)
- **YouTube cookies** for duration check via Webshare proxy
- **Uniform-cut fallback** when Claude-selected segments fail validation
- **Copyright detect-and-fallback** when formatter refuses on lyrics/poetry
- **Watchdog with task_metrics** monitoring 5 metrics with edge-trigger alerts

### Observability
- Supabase table `task_metrics` records every job (final_status, cut_status, download_method, formatter_status, processing_time_sec)
- Admin bot `/metrics` command shows last hour aggregates
- Watchdog runs hourly, alerts at <90% success or >30% fallback rate
- Recovery messages when metrics return to healthy

---

## Production Test Results (25.04.2026)

| # | Scenario | Result | Time |
|---|---|---|---|
| 1 | YouTube + 5 min + Transcript+Cut | PASS | ~2 min |
| 2 | YouTube + 5 min + Cut+SRT (after retry) | PASS | ~6 min |
| 3 | YouTube + No cut + Transcript only (Rick Astley copyright case) | PASS — copyright fallback delivered raw transcript | ~2 min |

End-to-end metrics confirmed 26.04.2026: 1 task in task_metrics with cut_success_rate=100%, download_method=supadata, formatter_status=success.

---

## Tech Stack

- **Backend:** FastAPI, Python 3.11, uvicorn, async/await
- **Bot:** python-telegram-bot v21 (job-queue extra)
- **Database:** Supabase (PostgreSQL + REST + auth)
- **Hosting:** Railway (us-west2)
- **AI:** Anthropic Claude Sonnet 4, Groq Whisper-large-v3-turbo
- **Media:** ffmpeg (H.264+AAC unified output), yt-dlp, Cobalt
- **Payments:** YuKassa (ShopID 1302226)
- **Proxy:** Webshare rotating proxy

---

## Versioning

Tag format: `v{major}.{minor}.{patch}-{scope}` where scope distinguishes products.

| Tag | Repo | Commit | Date |
|---|---|---|---|
| v1.0.0-telegram | transkrib-api | f2010ec | 26.04.2026 |
| v1.0.0-telegram | transkrib-bot | 695b73a | 26.04.2026 |
| v1.0.0-telegram | transkrib-admin-bot | 2176af6 | 26.04.2026 |
| desktop-v1.0.1 | transkrib-api (historical) | 256acb9 | 31.03.2026 |

---

## Roadmap (next)

### v1.1.0 — Multi-source download
- VK video download (with VK API integration)
- Rutube download
- Direct MP3/MP4 URLs
- Telegram-uploaded files

### v1.2.0 — Internationalization
- Per-language frontends (India, China, Korea, Brazil)
- Dedicated international marketing

### v2.0.0 — Pricing tiers production
- Trial 0 RUB/7d/30min, Basic 450 RUB/30d/300min, Standard 1700 RUB/30d/1500min, Pro 8900 RUB/365d/24000min
- Overflow packages
- 90% warning UX

### Other backlog
- Transcript chunking fix (>3500 char Telegram message split)
- VK timeout diagnosis
- get_title cookies path
- Balances monitoring extension (5%/20% thresholds for API balances)

---

## Credits

Built by Gennady with AI-assisted development (Cursor + Claude). Stabilization sprint 25-26.04.2026.
