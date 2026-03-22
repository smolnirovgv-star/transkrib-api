"""Preview image generation via Stability AI."""

import logging
from pathlib import Path

logger = logging.getLogger('video_processor.preview_service')


def generate_preview(text: str, output_path: Path) -> Path | None:
    """
    Generate preview image using Stability AI.
    Runs synchronously (call from a thread or asyncio.to_thread).
    Returns path to saved image, or None on failure.
    """
    from ..config import settings
    if not settings.stability_api_key:
        logger.info('Stability AI key not configured — preview skipped')
        return None

    prompt = text[:200].strip()
    if not prompt:
        return None

    try:
        import urllib.request
        import urllib.error
        import json

        url = 'https://api.stability.ai/v2beta/stable-image/generate/core'
        boundary = 'TranskribBoundary'
        body_parts = [
            f'--{boundary}
Content-Disposition: form-data; name="prompt"

{prompt}
',
            f'--{boundary}
Content-Disposition: form-data; name="output_format"

jpeg
',
            f'--{boundary}
Content-Disposition: form-data; name="aspect_ratio"

16:9
',
            f'--{boundary}--
',
        ]
        body = (''.join(body_parts)).encode('utf-8')

        req = urllib.request.Request(url, data=body, method='POST')
        req.add_header('Authorization', f'Bearer {settings.stability_api_key}')
        req.add_header('Accept', 'image/*')
        req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')

        import socket
        socket.setdefaulttimeout(30)
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 200:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(resp.read())
                logger.info(f'Preview saved: {output_path}')
                return output_path
            else:
                logger.error(f'Stability AI HTTP {resp.status}')
                return None

    except Exception as e:
        logger.error(f'Preview generation failed: {e}')
        return None
