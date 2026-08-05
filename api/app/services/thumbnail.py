from __future__ import annotations

import subprocess
from pathlib import Path


def thumbnail_path_for(video_path: Path) -> Path:
    """Thumbnail fica ao lado do vídeo, mesmo stem, extensão .jpg."""
    return video_path.with_suffix(".jpg")


def generate_thumbnail(video_path: Path, at_seconds: float = 1.0) -> Path:
    """Extrai um frame do vídeo e salva como JPEG em downloads."""
    if not video_path.is_file():
        raise FileNotFoundError(f"Vídeo não encontrado: {video_path}")

    thumb = thumbnail_path_for(video_path)
    # Tenta no segundo pedido; se falhar (vídeo muito curto), tenta no início
    attempts = [max(0.0, at_seconds), 0.0]
    last_error = ""

    for ss in attempts:
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{ss:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(thumb),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0 and thumb.is_file() and thumb.stat().st_size > 0:
            return thumb
        last_error = result.stderr.strip() or "FFmpeg falhou ao gerar thumbnail"

    raise RuntimeError(last_error)
