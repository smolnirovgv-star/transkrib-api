"""Result file endpoints: list, download, stream, delete."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from ..config import settings
from ..models.schemas import ResultItem
from ..services.storage_service import StorageService
from ..services.ffmpeg_service import FFmpegService

router = APIRouter(prefix="/api/results", tags=["results"])


def _get_storage() -> StorageService:
    return StorageService(
        settings.upload_dir, settings.processing_dir,
        settings.result_dir, settings.log_dir,
    )


@router.get("/", response_model=list[ResultItem])
async def list_results():
    """List all result video files."""
    storage = _get_storage()
    try:
        ffmpeg = FFmpegService(settings.ffmpeg_path)
        results = storage.list_results(ffmpeg_get_duration=ffmpeg.get_duration)
    except Exception:
        results = storage.list_results()
    return [ResultItem(**r) for r in results]


@router.get("/{filename}/download")
async def download_result(filename: str):
    """Download a result video file."""
    storage = _get_storage()
    path = storage.get_result_path(filename)
    if not path:
        raise HTTPException(404, f"Result not found: {filename}")
    return FileResponse(
        path=str(path),
        filename=filename,
        media_type="video/mp4",
    )


@router.get("/{filename}/stream")
async def stream_result(filename: str, request: Request):
    """Stream a result video file with proper Range request support for seeking."""
    storage = _get_storage()
    path = storage.get_result_path(filename)
    if not path:
        raise HTTPException(404, f"Result not found: {filename}")

    file_size = path.stat().st_size
    range_header = request.headers.get("Range")

    if range_header:
        try:
            range_val = range_header.replace("bytes=", "").split("-")
            start = int(range_val[0]) if range_val[0] else 0
            end = int(range_val[1]) if len(range_val) > 1 and range_val[1] else file_size - 1
        except (ValueError, IndexError):
            start, end = 0, file_size - 1

        end = min(end, file_size - 1)
        chunk_size = end - start + 1

        def iter_range():
            with open(path, "rb") as f:
                f.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    data = f.read(min(1024 * 1024, remaining))
                    if not data:
                        break
                    yield data
                    remaining -= len(data)

        return StreamingResponse(
            iter_range(),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_size),
            },
        )

    def iter_file():
        with open(path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                yield chunk

    return StreamingResponse(
        iter_file(),
        media_type="video/mp4",
        headers={
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        },
    )


@router.delete("/{filename}")
async def delete_result(filename: str):
    """Delete a result file."""
    storage = _get_storage()
    path = storage.get_result_path(filename)
    if not path:
        raise HTTPException(404, f"Result not found: {filename}")
    path.unlink()
    return {"status": "deleted", "filename": filename}
