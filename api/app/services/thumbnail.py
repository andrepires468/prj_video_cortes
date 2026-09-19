from __future__ import annotations

import subprocess
from pathlib import Path

# Cabe em 320×320 sem distorcer (16:9 vira 320×180). JPEG q:v 6 (escala 2–31).
THUMB_MAX_WIDTH = 320
THUMB_MAX_HEIGHT = 320
THUMB_JPEG_QUALITY = 6
_SCALE_FILTER = (
    f"scale='min({THUMB_MAX_WIDTH},iw)':'min({THUMB_MAX_HEIGHT},ih)'"
    ":force_original_aspect_ratio=decrease:force_divisible_by=2"
)


def thumbnail_path_for(video_path: Path) -> Path:
    """Thumbnail fica ao lado do vídeo, mesmo stem, extensão .jpg."""
    return video_path.with_suffix(".jpg")


def generate_thumbnail(video_path: Path, at_seconds: float = 1.0) -> Path:
    """Extrai um frame do vídeo e salva como JPEG ao lado do arquivo."""
    return generate_thumbnail_to(video_path, thumbnail_path_for(video_path), at_seconds)


def image_fits_thumb_limit(width: int | None, height: int | None) -> bool:
    """True se a imagem já cabe no teto 320×320."""
    if not width or not height:
        return False
    return width <= THUMB_MAX_WIDTH and height <= THUMB_MAX_HEIGHT


def resize_thumbnail_image(src: Path, dest: Path) -> Path:
    """Redimensiona um JPEG existente para o teto, sem distorcer nem ampliar."""
    if not src.is_file():
        raise FileNotFoundError(f"Imagem não encontrada: {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-frames:v",
        "1",
        "-vf",
        _SCALE_FILTER,
        "-q:v",
        str(THUMB_JPEG_QUALITY),
        str(dest),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not dest.is_file() or dest.stat().st_size <= 0:
        dest.unlink(missing_ok=True)
        raise RuntimeError(result.stderr.strip() or "FFmpeg falhou ao redimensionar thumbnail")
    return dest


def generate_thumbnail_to(video_path: Path, dest: Path, at_seconds: float = 1.0) -> Path:
    """Extrai um frame para `dest` (pode ser temp; não assume pasta data/)."""
    if not video_path.is_file():
        raise FileNotFoundError(f"Vídeo não encontrado: {video_path}")

    thumb = dest
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
            "-vf",
            _SCALE_FILTER,
            "-q:v",
            str(THUMB_JPEG_QUALITY),
            str(thumb),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0 and thumb.is_file() and thumb.stat().st_size > 0:
            return thumb
        last_error = result.stderr.strip() or "FFmpeg falhou ao gerar thumbnail"

    raise RuntimeError(last_error)
