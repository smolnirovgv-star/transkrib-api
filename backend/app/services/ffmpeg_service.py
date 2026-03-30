"""FFmpeg operations: find, convert, cut, merge. Extracted from transkrib/main.py."""

import os
import sys
import shutil
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Callable

logger = logging.getLogger("video_processor.ffmpeg")


class FFmpegService:
    def __init__(self, ffmpeg_path: str | None = None):
        self.ffmpeg_path = ffmpeg_path or self._find_ffmpeg()
        if not self.ffmpeg_path:
            raise RuntimeError("FFmpeg not found")
        self.ffprobe_path = self._find_ffprobe(self.ffmpeg_path)
        # Ensure FFmpeg dir is in PATH for Whisper
        ffmpeg_dir = str(Path(self.ffmpeg_path).parent)
        if ffmpeg_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

    @staticmethod
    def _find_ffmpeg() -> str | None:
        # In frozen (PyInstaller) mode APP_FFMPEG_PATH is always set by standalone_server.py
        # so this method is not called. Search system paths only in dev/Docker mode.
        if getattr(sys, "frozen", False):
            bundled = os.environ.get("APP_FFMPEG_PATH")
            if bundled and Path(bundled).exists():
                return bundled
            raise RuntimeError(
                "FFmpeg not found in bundle. APP_FFMPEG_PATH must be set."
            )

        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            return ffmpeg
        if sys.platform == "win32":
            winget_path = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe"
            if winget_path.exists():
                return str(winget_path)
            winget_pkg = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
            if winget_pkg.exists():
                for p in winget_pkg.rglob("ffmpeg.exe"):
                    return str(p)
            program_files = Path("C:/ffmpeg/bin/ffmpeg.exe")
            if program_files.exists():
                return str(program_files)
        # Linux/Docker common paths
        for p in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
            if Path(p).exists():
                return p
        return None

    @staticmethod
    def _find_ffprobe(ffmpeg_path: str) -> str:
        ext = ".exe" if sys.platform == "win32" else ""
        ffprobe_path = Path(ffmpeg_path).parent / f"ffprobe{ext}"
        if ffprobe_path.exists():
            return str(ffprobe_path)
        found = shutil.which("ffprobe")
        return found or "ffprobe"

    def get_version(self) -> str | None:
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                first_line = result.stdout.split("\n")[0]
                return first_line
        except Exception:
            pass
        return None

    def get_duration(self, video_path: Path) -> float:
        cmd = [
            self.ffprobe_path, "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(video_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            try:
                return float(result.stdout.strip())
            except ValueError:
                pass
        return 0.0

    def convert_to_mp4(
        self,
        input_path: Path,
        output_path: Path,
        on_progress: Callable[[float], None] | None = None,
    ) -> bool:
        logger.info(f"Converting: {input_path.name} -> {output_path.name}")
        cmd = [
            self.ffmpeg_path, "-i", str(input_path),
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            "-y", str(output_path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            logger.error(f"Convert timeout: {input_path.name}")
            return False
        if result.returncode != 0:
            logger.error(f"Convert error {input_path.name}: {result.stderr[-500:]}")
            return False
        ok = output_path.exists() and output_path.stat().st_size > 0
        if ok and on_progress:
            on_progress(100.0)
        return ok

    def cut_fragment(self, video_path: Path, start: str, end: str, output_path: Path) -> bool:
        # Use stream copy - no re-encoding needed for cutting, ~100x faster on low-CPU servers
        cmd = [
            self.ffmpeg_path,
            "-ss", start, "-to", end,
            "-i", str(video_path),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-y", str(output_path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            logger.error(f"Cut timeout [{start}-{end}]")
            return False
        if result.returncode != 0:
            logger.error(f"Cut error [{start}-{end}]: {result.stderr[-300:]}")
            return False
        return output_path.exists() and output_path.stat().st_size > 0

    def cut_and_merge(
        self,
        video_path: Path,
        fragments: list[dict],
        output_path: Path,
        fade_duration: float = 0.5,
        on_progress: Callable[[int, int], None] | None = None,
        temp_dir: Path | None = None,
    ) -> bool:
        logger.info(f"Assembly: {len(fragments)} fragments -> {output_path.name}")
        if not fragments:
            return False

        td_kwargs = {"dir": str(temp_dir)} if temp_dir is not None else {}
        with tempfile.TemporaryDirectory(**td_kwargs) as tmp_dir:
            tmp = Path(tmp_dir)
            cut_files: list[Path] = []
            durations: list[float] = []

            for i, frag in enumerate(fragments):
                cut_path = tmp / f"frag_{i:03d}.mp4"
                if self.cut_fragment(video_path, frag["start"], frag["end"], cut_path):
                    dur = self.get_duration(cut_path)
                    if dur > 0:
                        cut_files.append(cut_path)
                        durations.append(dur)
                if on_progress:
                    on_progress(i + 1, len(fragments))

            if not cut_files:
                logger.error("No fragments were cut")
                return False

            if len(cut_files) == 1:
                shutil.copy2(str(cut_files[0]), str(output_path))
                return True

            success = self._merge_with_xfade(cut_files, durations, output_path, fade_duration)
            if not success:
                logger.warning("xfade failed, falling back to concat")
                success = self._merge_with_concat(cut_files, output_path, tmp)
            return success

    def _merge_with_xfade(
        self,
        cut_files: list[Path],
        durations: list[float],
        output_path: Path,
        fade_duration: float,
    ) -> bool:
        n = len(cut_files)
        inputs: list[str] = []
        for cf in cut_files:
            inputs.extend(["-i", str(cf)])

        filter_parts: list[str] = []
        audio_parts: list[str] = []

        for k in range(n - 1):
            in_v = f"[{k}:v]" if k == 0 else f"[xv{k}]"
            in_a = f"[{k}:a]" if k == 0 else f"[xa{k}]"
            out_v = f"[xv{k+1}]" if k < n - 2 else "[vout]"
            out_a = f"[xa{k+1}]" if k < n - 2 else "[aout]"

            offset = sum(durations[:k + 1]) - (k + 1) * fade_duration
            if offset < 0:
                offset = 0

            filter_parts.append(
                f"{in_v}[{k+1}:v]xfade=transition=fade:duration={fade_duration}:offset={offset:.3f}{out_v}"
            )
            audio_parts.append(
                f"{in_a}[{k+1}:a]acrossfade=d={fade_duration}{out_a}"
            )

        filter_complex = ";".join(filter_parts + audio_parts)
        cmd = [self.ffmpeg_path] + inputs + [
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            "-y", str(output_path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            logger.error("xfade merge timeout")
            return False
        if result.returncode != 0:
            logger.error(f"xfade merge error: {result.stderr[-500:]}")
            return False
        return output_path.exists() and output_path.stat().st_size > 0

    def _merge_with_concat(self, cut_files: list[Path], output_path: Path, tmp_dir: Path) -> bool:
        concat_file = tmp_dir / "concat.txt"
        with open(concat_file, "w", encoding="utf-8") as f:
            for cf in cut_files:
                safe_path = str(cf).replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")

        cmd = [
            self.ffmpeg_path, "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            "-y", str(output_path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            logger.error("concat merge timeout")
            return False
        if result.returncode != 0:
            logger.error(f"concat merge error: {result.stderr[-500:]}")
            return False
        return output_path.exists() and output_path.stat().st_size > 0
