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

    def _load_whisper_model(self, WhisperModel, cache_dir) -> object:
        """Try offline first, fall back to download."""
        import os as _os
        # Try offline (cached)
        try:
            _os.environ["HF_HUB_OFFLINE"] = "1"
            model = WhisperModel(
                self._model_name,
                device="cpu",
                compute_type="int8",
                download_root=str(cache_dir) if cache_dir else None,
                local_files_only=True,
            )
            logger.info(f"[Whisper] Loaded from cache: {cache_dir}")
            return model
        except Exception:
            pass
        finally:
            _os.environ.pop("HF_HUB_OFFLINE", None)
        # Not cached — download first time
        logger.info(f"[Whisper] Downloading model to: {cache_dir}")
        return WhisperModel(
            self._model_name,
            device="cpu",
            compute_type="int8",
            download_root=str(cache_dir) if cache_dir else None,
        )

    def ensure_model(self) -> None:
        """Loads faster-whisper model into memory on first call (lazy). Subsequent calls are no-ops."""
        if self._model is None:
            from faster_whisper import WhisperModel
            import os as _os
            # Determine cache dir: explicit path > env var > default HF cache
            cache_dir = self._download_root
            if cache_dir is None:
                _env = _os.environ.get("APP_WHISPER_CACHE_DIR")
                if _env:
                    cache_dir = Path(_env)
                    logger.info(f"faster-whisper: using APP_WHISPER_CACHE_DIR: {cache_dir}")
            if cache_dir is not None:
                cache_dir.mkdir(parents=True, exist_ok=True)
                _os.environ.setdefault("HF_HOME", str(cache_dir))
            self._model = self._load_whisper_model(WhisperModel, cache_dir)
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

        # Check if silero VAD model is available in the bundle
        import sys as _sys, os as _os
        _vad_available = True
        if getattr(_sys, "frozen", False):
            _vad_path = _os.path.join(_sys._MEIPASS, "faster_whisper", "assets", "silero_vad_v6.onnx")
            _vad_available = _os.path.exists(_vad_path)
            if not _vad_available:
                logger.warning(f"[Whisper] silero_vad_v6.onnx not found in bundle — using vad_filter=False")

        try:
            segments_gen, info = self._model.transcribe(
                str(video_path),
                beam_size=1,
                vad_filter=_vad_available,
            )
            language = info.language or "unknown"
            raw_segments_raw = list(segments_gen)  # materialise generator inside try (VAD loads here)
        except Exception as _vad_err:
            logger.warning(f"faster-whisper VAD error (retrying without VAD): {_vad_err}")
            try:
                segments_gen2, info2 = self._model.transcribe(
                    str(video_path),
                    beam_size=1,
                    vad_filter=False,
                )
                language = info2.language or "unknown"
                raw_segments_raw = list(segments_gen2)
            except Exception as _e2:
                logger.error(f"faster-whisper failed without VAD too: {_e2}")
                return "", "unknown", []

        raw_segments: list[dict] = []
        lines: list[str] = []
        for seg in raw_segments_raw:
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
