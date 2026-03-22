"""File storage management for uploads, results, and cleanup."""

import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from ..utils.file_utils import safe_filename, get_next_result_number
from ..utils.time_utils import format_time

logger = logging.getLogger("video_processor.storage")


class StorageService:
    def __init__(self, upload_dir: Path, processing_dir: Path, result_dir: Path, log_dir: Path):
        self.upload_dir = upload_dir
        self.processing_dir = processing_dir
        self.result_dir = result_dir
        self.log_dir = log_dir
        # Create dirs
        for d in [self.upload_dir, self.processing_dir, self.result_dir, self.log_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def save_upload(self, filename: str, content: bytes) -> tuple[Path, str]:
        """Saves uploaded file. Returns (file_path, task_id)."""
        task_id = uuid.uuid4().hex[:12]
        task_dir = self.upload_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        file_path = task_dir / filename
        with open(file_path, "wb") as f:
            f.write(content)
        logger.info(f"Upload saved: {filename} -> {task_id}")
        return file_path, task_id

    def save_upload_stream(self, filename: str, file_obj) -> tuple[Path, str]:
        """Saves uploaded file from a file-like object. Returns (file_path, task_id)."""
        task_id = uuid.uuid4().hex[:12]
        task_dir = self.upload_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        file_path = task_dir / filename
        with open(file_path, "wb") as f:
            while chunk := file_obj.read(1024 * 1024):  # 1MB chunks
                f.write(chunk)
        logger.info(f"Upload saved: {filename} -> {task_id}")
        return file_path, task_id

    def get_processing_dir(self, task_id: str) -> Path:
        """Returns (and creates) a processing directory for a task."""
        d = self.processing_dir / task_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def generate_result_filename(self, original_name: str) -> str:
        """Generates NNN_YYYY-MM-DD_name.mp4 filename."""
        num = get_next_result_number(self.result_dir)
        date_str = datetime.now().strftime("%Y-%m-%d")
        name = safe_filename(original_name) or f"video_{num}"
        return f"{num:03d}_{date_str}_{name}.mp4"

    def get_result_path(self, filename: str) -> Path | None:
        """Returns full path to result file if it exists."""
        path = self.result_dir / filename
        return path if path.exists() else None

    def list_results(self, ffmpeg_get_duration=None) -> list[dict]:
        """Lists all result MP4 files with metadata."""
        results = []
        for f in sorted(self.result_dir.glob("*.mp4"), reverse=True):
            stat = f.stat()
            duration = 0.0
            if ffmpeg_get_duration:
                duration = ffmpeg_get_duration(f)
            results.append({
                "filename": f.name,
                "size_mb": round(stat.st_size / (1024 * 1024), 1),
                "duration_seconds": duration,
                "duration_formatted": format_time(duration),
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            })
        return results

    def cleanup_task(self, task_id: str) -> None:
        """Removes temp files for a task."""
        for base in [self.upload_dir, self.processing_dir]:
            task_dir = base / task_id
            if task_dir.exists():
                shutil.rmtree(task_dir, ignore_errors=True)
        logger.info(f"Cleaned up task: {task_id}")

    def get_storage_used_mb(self) -> float:
        """Returns total storage used in MB."""
        total = 0
        for d in [self.upload_dir, self.processing_dir, self.result_dir]:
            if d.exists():
                for f in d.rglob("*"):
                    if f.is_file():
                        total += f.stat().st_size
        return round(total / (1024 * 1024), 1)
