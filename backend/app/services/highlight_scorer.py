"""Per-phrase importance scoring via Claude API + fragment grouping."""

import json
import logging
from typing import Any

logger = logging.getLogger("video_processor.highlight_scorer")

SCORE_PROMPT = """Ты анализируешь транскрипцию видео.
Оцени важность каждой фразы от 1 до 10.

Критерии высокой оценки (8-10):
- Ключевые идеи, выводы, инсайты
- Приветствие и прощание спикера → ВСЕГДА 9-10
- Конкретные факты, цифры, советы
- Эмоциональные моменты

Критерии низкой оценки (1-3):
- Слова-паразиты ("эм", "ну", "так сказать")
- Повторения
- Технические паузы

Фразы для оценки:
{phrases_json}

Верни только JSON массив без пояснений:
[{{"index": 0, "score": 8, "reason": "ключевой вывод"}}, ...]"""


def score_phrases(
    phrases: list[dict],
    api_key: str,
    model: str,
    max_tokens: int = 4096,
    user_brief: dict | None = None,
) -> list[dict]:
    """
    Score each phrase via Claude API.
    Adds 'score' and 'reason' fields to each phrase dict.
    Falls back to score=5 on error.
    """
    if not phrases:
        return phrases

    import anthropic

    # Build compact input for Claude
    phrases_input = [{"index": i, "text": p["text"][:200]} for i, p in enumerate(phrases)]
    
    user_context = ""
    if user_brief:
        desc = user_brief.get("description", "").strip()
        kw = user_brief.get("keywords", "").strip()
        st = user_brief.get("style", "auto")
        if desc or kw or st != "auto":
            user_context = f"""
Дополнительные пожелания пользователя:
{desc}

Ключевые слова для приоритета: {kw}

Стиль нарезки: {st}

ВАЖНО: Учитывай эти пожелания при оценке важности фраз.
Фразы содержащие ключевые слова получают +2 к оценке.
"""
    
    prompt = SCORE_PROMPT.format(phrases_json=json.dumps(phrases_input, ensure_ascii=False, indent=2))
    if user_context:
        prompt = user_context.strip() + "

" + prompt

    score_map = {}
    try:
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.content[0].text.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])
        scored_list = json.loads(response_text)
        score_map = {item["index"]: item for item in scored_list if "index" in item}
    except Exception as e:
        logger.error(f"Claude scoring failed: {e} — using fallback score=5")
        score_map = {}

    result = []
    for i, phrase in enumerate(phrases):
        s = score_map.get(i, {})
        result.append({
            **phrase,
            "score": s.get("score", 5),
            "reason": s.get("reason", ""),
        })
    logger.info(f"Scored {len(result)} phrases, avg={sum(p['score'] for p in result)/max(len(result),1):.1f}")
    return result


def group_fragments(
    scored_phrases: list[dict],
    duration: float,
    ratio_min: float = 0.20,
    ratio_max: float = 0.60,
    max_seconds: int = 900,
    intro_duration: int = 60,
    ending_duration: int = 60,
) -> list[dict]:
    """
    Group scored phrases into video fragments for FFmpeg.
    Returns [{start: "HH:MM:SS", end: "HH:MM:SS"}, ...]
    """
    from ..utils.time_utils import format_time

    if not scored_phrases:
        return []

    GREETING_WINDOW = 30.0  # first/last N seconds always included
    MIN_CLIP = 10.0
    MERGE_GAP = 3.0  # merge clips if gap <= this

    # Mark selected phrases
    selected = []
    for p in scored_phrases:
        is_greeting = p["start"] < GREETING_WINDOW or p["end"] > (duration - GREETING_WINDOW)
        if p["score"] >= 6 or is_greeting:
            selected.append(p)

    if not selected:
        # Fallback: top 30% by score
        sorted_p = sorted(scored_phrases, key=lambda x: x["score"], reverse=True)
        selected = sorted_p[:max(1, len(sorted_p) // 3)]
        selected.sort(key=lambda x: x["start"])

    # Merge consecutive selected phrases into clips
    clips = []
    cur_start = selected[0]["start"]
    cur_end = selected[0]["end"]

    for p in selected[1:]:
        gap = p["start"] - cur_end
        if gap <= MERGE_GAP:
            cur_end = p["end"]
        else:
            clips.append((cur_start, cur_end))
            cur_start = p["start"]
            cur_end = p["end"]
    clips.append((cur_start, cur_end))

    # Enforce min clip duration
    merged = []
    i = 0
    while i < len(clips):
        s, e = clips[i]
        dur = e - s
        if dur < MIN_CLIP and i + 1 < len(clips):
            # Extend to next clip
            next_s, next_e = clips[i + 1]
            merged.append((s, next_e))
            i += 2
        else:
            merged.append((s, e))
            i += 1

    # Enforce max total duration
    target_max = min(duration * ratio_max, max_seconds)
    total = sum(e - s for s, e in merged)
    if total > target_max:
        # Trim least-scored clips
        clip_scores = []
        for s, e in merged:
            phrases_in = [p for p in scored_phrases if p["start"] >= s and p["end"] <= e]
            avg = sum(p["score"] for p in phrases_in) / max(len(phrases_in), 1)
            clip_scores.append((avg, s, e))
        clip_scores.sort(reverse=True)
        keep = []
        kept_dur = 0.0
        for score, s, e in clip_scores:
            if kept_dur + (e - s) <= target_max:
                keep.append((s, e))
                kept_dur += e - s
        merged = sorted(keep, key=lambda x: x[0])

    # Force include intro (first intro_duration seconds)
    intro_end = min(float(intro_duration), duration)
    intro_included = any(s <= float(intro_duration) for s, e in merged)
    if not intro_included and duration > 0:
        merged.append((0.0, intro_end))
        logger.info(f"group_fragments: forced intro 0..{intro_end:.0f}s")

    # Force include ending (last ending_duration seconds)
    ending_start = max(0.0, duration - float(ending_duration))
    ending_included = any(e >= ending_start for s, e in merged)
    if not ending_included and duration > 0:
        merged.append((ending_start, duration))
        logger.info(f"group_fragments: forced ending {ending_start:.0f}..{duration:.0f}s")

    # Re-sort after forced additions
    merged.sort(key=lambda x: x[0])

    fragments = [{"start": format_time(s), "end": format_time(e)} for s, e in merged]
    total_hl = sum(e - s for s, e in [(p[0], p[1]) for p in [(cs, ce) for cs, ce in [(x["start"], x["end"]) for x in fragments]]])
    logger.info(f"group_fragments: {len(fragments)} clips from scored phrases")
    return fragments
