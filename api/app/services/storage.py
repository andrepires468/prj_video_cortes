from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from app.config import settings
from app.models.schemas import FileInfo
from app.services.filenames import safe_video_stem

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


def _assert_safe_filename(filename: str) -> None:
    if not filename or filename.strip() != filename:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido")
    if "/" in filename or "\\" in filename or filename in {".", ".."}:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido")


def _resolve_in_dir(directory: Path, filename: str) -> Path:
    """Resolve a file inside directory, blocking path traversal."""
    _assert_safe_filename(filename)
    base = directory.resolve()
    candidate = (base / filename).resolve()
    if not str(candidate).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Caminho inválido")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return candidate


def resolve_media_file(filename: str, folder: str = "downloads") -> Path:
    if folder == "cortes":
        return _resolve_in_dir(ensure_cortes_dir(), filename)
    if folder == "downloads":
        return _resolve_in_dir(ensure_downloads_dir(), filename)
    raise HTTPException(status_code=400, detail="Pasta inválida")


def resolve_download_file(filename: str) -> Path:
    """Resolve a file inside downloads dir, blocking path traversal."""
    return resolve_media_file(filename, "downloads")


def list_files() -> list[FileInfo]:
    directory = ensure_downloads_dir()
    files: list[FileInfo] = []
    for entry in directory.iterdir():
        if not entry.is_file():
            continue
        info = _video_file_info(entry)
        if info:
            files.append(info)
    files.sort(key=lambda f: f.mtime, reverse=True)
    return files


def list_cortes(source_filename: str) -> list[FileInfo]:
    """Lista cortes em data/cortes gerados a partir do vídeo de origem."""
    _assert_safe_filename(source_filename)
    prefix = f"{safe_video_stem(source_filename)}_corte_"
    directory = ensure_cortes_dir()
    files: list[FileInfo] = []
    for entry in directory.iterdir():
        if not entry.is_file():
            continue
        if not entry.stem.startswith(prefix):
            continue
        info = _video_file_info(entry)
        if info:
            files.append(info)
    files.sort(key=lambda f: f.mtime, reverse=True)
    return files


def corte_belongs_to(original_filename: str, corte_filename: str) -> bool:
    """True se o arquivo em cortes foi gerado a partir do download informado."""
    _assert_safe_filename(original_filename)
    _assert_safe_filename(corte_filename)
    prefix = f"{safe_video_stem(original_filename)}_corte_"
    return Path(corte_filename).stem.startswith(prefix)


def _video_file_info(entry: Path) -> FileInfo | None:
    if entry.name.startswith("."):
        return None
    if entry.name.endswith((".part", ".ytdl", ".temp")):
        return None
    if entry.suffix.lower() not in VIDEO_EXTENSIONS:
        return None

    thumb_name: str | None = None
    thumb_candidate = entry.with_suffix(".jpg")
    if thumb_candidate.is_file():
        thumb_name = thumb_candidate.name

    stat = entry.stat()
    return FileInfo(
        name=entry.name,
        size=stat.st_size,
        mtime=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
        thumb=thumb_name,
    )


def _unlink_video_and_thumb(path: Path) -> None:
    thumb = path.with_suffix(".jpg")
    if path.is_file():
        path.unlink()
    if thumb.is_file():
        thumb.unlink()


def delete_media(filename: str, folder: str = "downloads") -> tuple[str, int]:
    """Remove o vídeo e a thumbnail. Em downloads, remove também os cortes associados."""
    if folder == "cortes":
        path = resolve_media_file(filename, "cortes")
        _unlink_video_and_thumb(path)
        return filename, 0

    if folder != "downloads":
        raise HTTPException(status_code=400, detail="Pasta inválida")

    path = resolve_download_file(filename)
    cortes_deleted = 0
    for corte in list_cortes(filename):
        try:
            corte_path = resolve_media_file(corte.name, "cortes")
        except HTTPException:
            continue
        _unlink_video_and_thumb(corte_path)
        cortes_deleted += 1
    _unlink_video_and_thumb(path)
    return filename, cortes_deleted


def is_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS
