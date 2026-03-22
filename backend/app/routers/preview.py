"""Preview generation endpoint."""

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..config import settings

router = APIRouter(prefix='/api/preview', tags=['preview'])
logger = logging.getLogger('video_processor.preview_router')


class PreviewRequest(BaseModel):
    filename: str


@router.post('/generate')
async def generate_preview_endpoint(req: PreviewRequest):
    """Generate AI preview image for a result video."""
    stem = Path(req.filename).stem
    preview_path = settings.result_dir / f'{stem}_preview.jpg'

    # Return cached preview if already exists
    if preview_path.exists():
        return {'preview_url': f'/api/preview/image/{stem}_preview.jpg'}

    # Load transcript if saved by pipeline
    transcript_path = settings.result_dir / f'{stem}_transcript.txt'
    if transcript_path.exists():
        text = transcript_path.read_text(encoding='utf-8')
    else:
        # Fallback: use cleaned filename stem as prompt
        text = stem.replace('_', ' ').replace('-', ' ')

    from ..services.preview_service import generate_preview
    result = await asyncio.to_thread(generate_preview, text, preview_path)

    if result:
        return {'preview_url': f'/api/preview/image/{stem}_preview.jpg'}
    return {'preview_url': None}


@router.get('/image/{filename}')
async def get_preview_image(filename: str):
    """Serve a preview JPEG."""
    if not filename.endswith('_preview.jpg'):
        raise HTTPException(404, 'Not found')
    path = settings.result_dir / filename
    if not path.exists():
        raise HTTPException(404, 'Preview not found')
    return FileResponse(str(path), media_type='image/jpeg')
