"""Claude API analysis service. Extracted from transkrib/main.py."""

import json
import logging

import anthropic

from ..utils.time_utils import format_time, parse_time
from ..config import settings

logger = logging.getLogger("video_processor.analysis")

HIGHLIGHTS_PROMPT = """Ты — профессиональный видеоредактор. Проанализируй транскрипт видео с таймкодами и выбери ключевые смысловые эпизоды.

Общая длительность видео: {duration}
Целевая длительность итогового видео: примерно {target_duration} (10-15% от оригинала, не более 15 минут)

Транскрипт:
{transcript}

Правила выбора фрагментов:
1. Если в начале видео (в первые 2 минуты) спикер приветствует аудиторию или представляется — ОБЯЗАТЕЛЬНО включи этот фрагмент целиком.
2. Если в конце видео (последние 2 минуты) спикер прощается с аудиторией — ОБЯЗАТЕЛЬНО включи этот фрагмент целиком.
3. Между приветствием и прощанием выбери наиболее ключевые и содержательные моменты, чтобы итоговое видео укладывалось в целевую длительность.
4. Фрагменты должны быть логически завершёнными — не обрывай мысль на середине.

Верни ТОЛЬКО валидный JSON-массив в формате:
[
    {{"start": "00:05:10", "end": "00:08:45"}},
    {{"start": "00:12:00", "end": "00:14:30"}}
]

Отвечай ТОЛЬКО валидным JSON, без дополнительного текста."""


class AnalysisService:
    def __init__(self, api_key: str, model: str, max_tokens: int):
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self._model = model
        self._max_tokens = max_tokens

    @property
    def model_name(self) -> str:
        return self._model

    def analyze_highlights(
        self,
        transcript: str,
        duration_seconds: float,
        ratio_min: float = 0.10,
        ratio_max: float = 0.15,
        max_seconds: int = 900,
    ) -> list[dict] | None:
        """
        Sends transcript to Claude API to select key episodes.
        Returns list of {start, end} dicts or None on failure.
        """
        logger.info("Analyzing via Claude API")

        target_seconds = min(duration_seconds * ratio_max, max_seconds)
        target_seconds = max(target_seconds, duration_seconds * ratio_min)
        target_duration = format_time(target_seconds)
        duration_str = format_time(duration_seconds)

        trimmed = transcript
        if len(trimmed) > 50000:
            trimmed = trimmed[:50000] + "\n\n[...транскрипт обрезан...]"

        prompt = HIGHLIGHTS_PROMPT.format(
            transcript=trimmed,
            duration=duration_str,
            target_duration=target_duration,
        )

        message = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        if not message.content:
            logger.error("Claude returned empty content")
            return None
        response_text = message.content[0].text.strip()

        try:
            if response_text.startswith("```"):
                resp_lines = response_text.split("\n")
                response_text = "\n".join(resp_lines[1:-1])
            fragments = json.loads(response_text)
            if not isinstance(fragments, list):
                raise ValueError("Expected JSON array")
            for frag in fragments:
                if "start" not in frag or "end" not in frag:
                    raise ValueError(f"Missing start/end: {frag}")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Claude parse error: {e}\nResponse: {response_text[:500]}")
            return None

        # Force include intro (first intro_duration seconds)
        intro_end = min(float(settings.intro_duration), duration_seconds)
        intro_included = any(parse_time(f["start"]) <= float(settings.intro_duration) for f in fragments)
        if not intro_included and duration_seconds > 0:
            fragments.append({"start": format_time(0.0), "end": format_time(intro_end)})
            logger.info(f"analyze_highlights: forced intro 0..{intro_end:.0f}s")

        # Force include ending (last ending_duration seconds)
        ending_start = max(0.0, duration_seconds - float(settings.ending_duration))
        ending_included = any(parse_time(f["end"]) >= ending_start for f in fragments)
        if not ending_included and duration_seconds > 0:
            fragments.append({"start": format_time(ending_start), "end": format_time(duration_seconds)})
            logger.info(f"analyze_highlights: forced ending {ending_start:.0f}..{duration_seconds:.0f}s")

        fragments.sort(key=lambda f: parse_time(f["start"]))

        total_hl = sum(parse_time(f["end"]) - parse_time(f["start"]) for f in fragments)
        logger.info(f"Claude selected {len(fragments)} fragments ({format_time(total_hl)})")
        return fragments
