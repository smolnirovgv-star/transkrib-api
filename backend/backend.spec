# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Transkrib standalone backend.

Usage:
    pyinstaller backend.spec --clean --noconfirm

Output:
    dist/backend/backend.exe + all dependencies (~600-800MB)
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

# Paths
SPEC_DIR = Path(SPECPATH)
BACKEND_DIR = SPEC_DIR
APP_DIR = BACKEND_DIR / "app"

# Icon (optional — build proceeds without it if missing)
_icon_path = BACKEND_DIR.parent / 'platforms' / 'desktop_windows' / 'build' / 'icon.ico'
APP_ICON = str(_icon_path) if _icon_path.exists() else None

# FFmpeg binaries (from WinGet installation)
FFMPEG_BIN = Path(r"C:\Users\Admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin")

# yt-dlp executable
YTDLP_EXE = Path(r"C:\Users\Admin\AppData\Local\Programs\Python\Python311\Scripts\yt-dlp.exe")

# Collect faster-whisper data files (VAD model, assets)
faster_whisper_datas = [
    (r'C:/Users/Admin/AppData/Local/Programs/Python/Python311/Lib/site-packages/faster_whisper/assets',
     'faster_whisper/assets'),
]

# Analysis
a = Analysis(
    [str(BACKEND_DIR / 'standalone_server.py')],
    pathex=[str(BACKEND_DIR)],
    binaries=[
        # FFmpeg + FFprobe (critical for video processing)
        (str(FFMPEG_BIN / 'ffmpeg.exe'), 'ffmpeg'),
        (str(FFMPEG_BIN / 'ffprobe.exe'), 'ffmpeg'),

        # yt-dlp standalone executable
        (str(YTDLP_EXE), '.'),
    ],
    datas=[
        # faster-whisper assets (VAD silero model)
        *faster_whisper_datas,
    ],
    hiddenimports=[
        # FastAPI ecosystem
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'fastapi',
        'starlette',
        'starlette.responses',
        'starlette.routing',
        'starlette.middleware',
        'pydantic',
        'pydantic_settings',
        'pydantic.fields',
        'pydantic.main',
        'pydantic.types',
        'multipart',
        'python_multipart',

        # faster-whisper + ctranslate2
        'faster_whisper',
        'ctranslate2',
        'numpy',
        'numpy.core',
        'tqdm',

        # App modules
        'app',
        'app.config',
        'app.license',
        'app.trial',
        'app.fingerprint',
        'app.pipeline',
        'app.routers.results',
        'app.routers.system',
        'app.routers.standalone_tasks_router',
        'app.routers.standalone_ws_router',
        'app.services.ffmpeg_service',
        'app.services.download_service',
        'app.services.transcription_service',
        'app.services.analysis_service',
        'app.services.storage_service',
        'app.workers.memory_progress',
        'app.workers.standalone_tasks',
        'app.websocket.memory_manager',
        'app.models.schemas',
        'app.models.enums',
        'app.utils.time_utils',
        'app.utils.file_utils',
        'app.services.pause_detector',
        'app.services.highlight_scorer',
        'app.services.preview_service',
        'app.routers.preview',
        'app.routers.transcript',

        # Anthropic SDK
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'requests',
        'anthropic',
        'anthropic.types',
        'anthropic.resources',

        # yt-dlp (as module, даже если используем .exe)
        'yt_dlp',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude Celery/Redis (не используются в standalone)
        'celery',
        'redis',
        'kombu',
        'billiard',
        'amqp',
        'vine',

        # Exclude GUI libraries (не нужны)
        'tkinter',
        'matplotlib',
        'IPython',
        'notebook',

        # Exclude test frameworks
        'pytest',
        '_pytest',

        # Exclude dev tools
        'black',
        'mypy',
        'pylint',
    ],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

# PYZ archive
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# EXE
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # Use --onedir mode (не --onefile)
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # CRITICAL: UPX breaks PyTorch DLLs on Windows
    console=True,  # Show console for debugging (set False for production if desired)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=APP_ICON,
)

# COLLECT — create dist/backend/ directory with all files
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='backend',
)
