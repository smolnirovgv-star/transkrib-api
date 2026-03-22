"""Whisper transcription service. Extracted from transkrib/main.py."""

import logging
from pathlib import Path
from typing import Callable

from ..utils.time_utils import format_time

logger = logging.getLogger("video_processor.transcription")


class TranscriptionService:
    def __init__(self, model_name: str = "small", download_root: Path | None = None):
        self._model_name = model_name
        self._download_root = download_root
        self._model = None

    def ensure_model(self) -> None:
        """Loads faster-whisper model into memory on first call (lazy). Subsequent calls are no-ops."""
        if self._model is None:
            from faster_whisper import WhisperModel
            import os as _os
            # Determine cache dir: use explicit path, env var, or default HF cache
            download_root = self._download_root
            if download_root is None:
                _env = _os.environ.get("APP_WHISPER_CACHE_DIR")
                if _env:
                    download_root = Path(_env)
                    logger.info(f"faster-whisper: using APP_WHISPER_CACHE_DIR: {download_root}")
            if download_root is not None:
                download_root.mkdir(parents=True, exist_ok=True)
                _os.environ.setdefault("HF_HOME", str(download_root))
                logger.info(f"faster-whisper cache dir: {download_root}")
            logger.info(f"Loading faster-whisper model: {self._model_name} ...")
            self._model = WhisperModel(self._model_name, device="cpu", compute_type="int8")
            logger.info(f"faster-whisper model '{self._model_name}' ready")

    @property
    def model_name(self) -> str:
        return self._model_name

    def transcribe(
        self,
        video_path: Path,
        on_progress: Callable[[str], None] | None = None,
    ) -> tuple[str, str, list[dict]]:
        """
        Transcribes video/audio file via Whisper with timestamps.
        Returns (transcript_text, language, raw_segments).
        Transcript format: [HH:MM:SS - HH:MM:SS] text per line.
        """
        self.ensure_model()
        logger.info(f"Transcribing: {video_path.name}")
        if on_progress:
            on_progress("starting")

        segments_gen, info = self._model.transcribe(
            str(video_path),
            beam_size=1,
            vad_filter=True,
        )
        language = info.language or "unknown"

        raw_segments: list[dict] = []
        lines: list[str] = []
        for seg in segments_gen:
            start = format_time(seg.start)
            end = format_time(seg.end)
            text = seg.text.strip()
            if text:
                lines.append(f"[{start} - {end}] {text}")
                raw_segments.append({"text": text, "start": seg.start, "end": seg.end})

        transcript_text = "\n".join(lines)

        # Save transcript next to video
        txt_path = video_path.with_suffix(".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(transcript_text)

        logger.info(f"Transcription done: {len(lines)} segments, {language}")
        if on_progress:
            on_progress("done")

        return transcript_text, language, raw_segments
