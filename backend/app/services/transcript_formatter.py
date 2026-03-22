"""Transcript formatting via Claude API."""

import logging
from pathlib import Path

logger = logging.getLogger("video_processor.transcript_formatter")

_FORMAT_PROMPT = (
    "\u0422\u044b \u0440\u0435\u0434\u0430\u043a\u0442\u043e\u0440 \u0442\u0435\u043a\u0441\u0442\u0430."
    " \u041e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u0439 \u0442\u0440\u0430\u043d\u0441\u043a\u0440\u0438\u043f\u0446\u0438\u044e \u0440\u0435\u0447\u0438:\n\n"
    "1. \u0423\u0431\u0435\u0440\u0438 \u0441\u043b\u043e\u0432\u0430-\u043f\u0430\u0440\u0430\u0437\u0438\u0442\u044b"
    " (\u043d\u0443, \u0432\u043e\u0442, \u0437\u043d\u0430\u0447\u0438\u0442, \u044d-\u044d, \u0434\u0430, \u043f\u043e\u043d\u0438\u043c\u0430\u0435\u0442\u0435)\n"
    "2. \u0420\u0430\u0441\u0441\u0442\u0430\u0432\u044c \u0437\u043d\u0430\u043a\u0438 \u043f\u0440\u0435\u043f\u0438\u043d\u0430\u043d\u0438\u044f"
    " \u043f\u043e \u043f\u0440\u0430\u0432\u0438\u043b\u0430\u043c \u044f\u0437\u044b\u043a\u0430 \u043e\u0440\u0438\u0433\u0438\u043d\u0430\u043b\u0430\n"
    "3. \u0420\u0430\u0437\u0434\u0435\u043b\u0438 \u043d\u0430 \u0430\u0431\u0437\u0430\u0446\u044b \u043f\u043e \u0441\u043c\u044b\u0441\u043b\u0443"
    " (\u043a\u0430\u0436\u0434\u0430\u044f \u043d\u043e\u0432\u0430\u044f \u043c\u044b\u0441\u043b\u044c \u2014 \u043d\u043e\u0432\u044b\u0439 \u0430\u0431\u0437\u0430\u0446)\n"
    "4. \u0418\u0441\u043f\u0440\u0430\u0432\u044c \u043e\u0440\u0444\u043e\u0433\u0440\u0430\u0444\u0438\u044e\n"
    "5. \u0421\u043e\u0445\u0440\u0430\u043d\u0438 \u0441\u0442\u0438\u043b\u044c \u0438 \u0441\u043b\u043e\u0432\u0430 \u0441\u043f\u0438\u043a\u0435\u0440\u0430"
    " \u2014 \u043d\u0435 \u043f\u0435\u0440\u0435\u043f\u0438\u0441\u044b\u0432\u0430\u0439 \u0441\u043c\u044b\u0441\u043b\n"
    "6. \u0412\u0435\u0440\u043d\u0438 \u0442\u043e\u043b\u044c\u043a\u043e \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u043d\u043d\u044b\u0439"
    " \u0442\u0435\u043a\u0441\u0442 \u0431\u0435\u0437 \u043f\u043e\u044f\u0441\u043d\u0435\u043d\u0438\u0439\n\n"
    "\u0422\u0440\u0430\u043d\u0441\u043a\u0440\u0438\u043f\u0446\u0438\u044f:\n{text}"
)


def format_transcript(
    text: str,
    api_key: str,
    model: str,
    cache_path: "Path | None" = None,
) -> str:
    """Format transcript via Claude API.

    Returns formatted text. Falls back to raw text on any error.
    Result is cached at cache_path to avoid repeated API calls.
    """
    if not text.strip():
        return text

    # Return cached result if available
    if cache_path and cache_path.exists():
        try:
            return cache_path.read_text(encoding="utf-8")
        except Exception:
            pass

    try:
        import anthropic

        prompt = _FORMAT_PROMPT.format(text=text)
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        message = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        formatted = message.content[0].text.strip()

        # Save to cache
        if cache_path:
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(formatted, encoding="utf-8")
            except Exception as e:
                logger.warning(f"Could not save formatted transcript cache: {e}")

        logger.info(f"Formatted transcript: {len(text)} chars -> {len(formatted)} chars")
        return formatted

    except Exception as e:
        logger.warning(f"Claude formatting failed: {e} -- using raw text")
        return text
