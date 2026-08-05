from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from app.config import settings
from app.models.schemas import FileInfo

VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def ensure_downloads_dir() -> Path:
    path = settings.downloads_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_cortes_dir() -> Path:
    path = settings.cortes_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_download_file(filename: str) -> Path:
    """Resolve a file inside downloads dir, blocking path traversal."""
    if not filename or filename.strip() != filename:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido")
    if "/" in filename or "\\" in filename or filename in {".", ".."}:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido")

    base = ensure_downloads_dir().resolve()
    candidate = (base / filename).resolve()
    if not str(candidate).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Caminho inválido")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return candidate


def list_files() -> list[FileInfo]:
    directory = ensure_downloads_dir()
    files: list[FileInfo] = []
    for entry in directory.iterdir():
        if not entry.is_file():
            continue
        if entry.name.startswith("."):
            continue
        if entry.name.endswith((".part", ".ytdl", ".temp")):
            continue
        # Lista só vídeos; thumbs .jpg ficam ocultas no grid
        if entry.suffix.lower() not in VIDEO_EXTENSIONS:
            continue

        thumb_name: str | None = None
        thumb_candidate = entry.with_suffix(".jpg")
        if thumb_candidate.is_file():
            thumb_name = thumb_candidate.name

        stat = entry.stat()
        files.append(
            FileInfo(
                name=entry.name,
                size=stat.st_size,
                mtime=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                thumb=thumb_name,
            )
        )
    files.sort(key=lambda f: f.mtime, reverse=True)
    return files


def is_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS
