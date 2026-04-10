"""Application configuration via environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Paths
    storage_dir: Path = Path(__file__).parent.parent / "storage"

    # External tools
    ffmpeg_path: str | None = None  # Auto-detect if None

    # Whisper
    whisper_model: str = "tiny"
    max_audio_duration: int = 600  # 10 min limit

    # Claude
    anthropic_api_key: str = ""

    # Stability AI
    stability_api_key: str = ""
    claude_model: str = "claude-sonnet-4-5-20250929"
    claude_max_tokens: int = 4096

    # Processing
    fade_duration: float = 0.5
    target_highlight_ratio_min: float = 0.10
    target_highlight_ratio_max: float = 0.15
    target_highlight_max_seconds: int = 900  # 15 minutes
    video_extensions: set[str] = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv"}

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Dev mode
    dev_mode: bool = False

    # Intro/ending forced inclusion
    intro_duration: int = 60   # always include first N seconds
    ending_duration: int = 60  # always include last N seconds

    # Server
    cors_origins: list[str] = ["*"]
    max_upload_size_mb: int = 2048

    model_config = {"env_file": ".env", "env_prefix": "APP_"}

    @property
    def whisper_cache_dir(self) -> Path:
        return self.storage_dir / "whisper_models"

    @property
    def temp_dir(self) -> Path:
        return self.storage_dir / "temp"

    @property
    def upload_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def processing_dir(self) -> Path:
        return self.storage_dir / "processing"

    @property
    def result_dir(self) -> Path:
        return self.storage_dir / "results"

    @property
    def log_dir(self) -> Path:
        return self.storage_dir / "logs"


settings = Settings()
