"""Startup tasks: update critical dependencies before server launch."""
import subprocess
import sys
import logging

logger = logging.getLogger(__name__)


def update_critical_dependencies():
    """Update critical dependencies at server startup.
    yt-dlp requires frequent updates as YouTube changes its API."""
    try:
        # Remove broken OAuth2 plugin (archived 17.01.2026)
        subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "-y", "yt-dlp-youtube-oauth2"],
            capture_output=True, timeout=30
        )
        logger.info("Removed yt-dlp-youtube-oauth2 plugin (if existed)")

        # Update yt-dlp to latest version
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            logger.info("yt-dlp updated successfully")
        else:
            logger.warning("yt-dlp update failed: %s", result.stderr[:300])

    except Exception as e:
        logger.warning("Failed to update dependencies: %s", e)
