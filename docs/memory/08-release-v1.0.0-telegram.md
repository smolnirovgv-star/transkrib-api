# Release v1.0.0-telegram — 26.04.2026

This file is the cross-session anchor for the v1.0.0-telegram release. Future Claude sessions should treat it as the "as of 26.04.2026" snapshot.

## What's released

Three-repo Telegram bot stack:
- transkrib-api @ f2010ec -> tag v1.0.0-telegram
- transkrib-bot @ 695b73a -> tag v1.0.0-telegram
- transkrib-admin-bot @ 2176af6 -> tag v1.0.0-telegram

## Production state confirmed

3/3 manual tests PASS on 25.04.2026 (PCZywVQ9ceQ Transcript+Cut, PCZywVQ9ceQ Cut+SRT after retry, dQw4w9WgXcQ Rick Astley copyright fallback).
End-to-end metrics confirmed 26.04.2026 — first task recorded in task_metrics with full status chain: download=supadata, cut=uniform_fallback, format=success, final=success, all 100%.

## What works

- YouTube download via 4-method chain (yt-dlp -> Supadata -> RapidAPI -> Cobalt)
- Uniform-cut fallback when Claude segments invalid (handles duration=0 edge case after fix c45564f)
- Copyright detect-and-fallback (raw transcript with prefix when formatter refuses)
- Whisper-large-v3-turbo transcription (auto/RU/EN)
- Claude Sonnet 4 formatting
- ffmpeg cut with H.264+AAC unified output
- YuKassa payments (ShopID 1302226)
- Invite codes via admin bot
- Watchdog with 5 metrics, edge-trigger alerts

## What's NOT released in v1.0.0-telegram (explicit non-scope)

- VK / Rutube / direct MP3-MP4 sources (planned v1.1.0)
- Per-language frontends (planned v1.2.0)
- Production pricing tiers (test branch only, planned v2.0.0)
- Balances monitoring (planned as backlog extension)
- Auto-failover via download_config table (planned v2.0+ watchdog enhancement)

## Open known bugs (non-blocking, deferred to v1.1+)

- Transcript truncation at ~3500 chars in bot.py (Telegram 4096 limit)
- VK timeout >10 min not diagnosed
- Cut button asks for URL again (state lost in ConversationHandler)
- get_title() in download_service.py:107 without cookies (low priority)
- Helper duplication _get_cookie_file/_prepare_ytdlp_cookies (tech debt)
- PTBUserWarnings per_message=False (cosmetic)
- task_metrics PRIMARY KEY conflict on retry (mitigated by upsert in metrics.py)

## Critical infrastructure

- Supabase: aakxqjpyikhjzkfvwppu
- Tables: task_metrics, invite_codes, bot_users, bot_chat_history, chat_history
- Railway project: gallant-healing (c8e80613)
- Railway services: transkrib-api (eb3eb8ff), transkrib-bot (158d6319), cobalt (7b831c27)
- transkrib-admin-bot deployed separately (Procfile worker)
- Production bots: @transkrib_smartcut_bot, @TranskribAdmin_Bot
- ADMIN_ID: 5052641158

## Stable rollback anchors

- v1.0.0-telegram (this release): the latest known-good
- stable-feat-pack-2026-04-25: pre-release stable (before metrics+watchdog)
- stable-intermediate-2026-04-25: mid-stabilization
- epoch/full-pipeline-with-payments-2026-04-22: deepest stable epoch

## Decision log relevant to this release

See 07-decisions-log.md entries for 2026-04-25 (uniform-cut algorithm A, copyright fallback, watchdog architecture, task_metrics schema, defensive metrics design).
