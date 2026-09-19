from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.db import SessionLocal
from app.models.orm import Corte, Download
from app.models.pagination import DEFAULT_PER_PAGE, PaginationMeta, paginate_query
from app.models.schemas import FileInfo, JobStatus, MediaInfo
from app.services import s3

_PRESIGN_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="s3-presign")


def _mtime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _try_presign_play(storage_key: str | None, name: str | None) -> str | None:
    if not storage_key or not name or not s3.playback_cors_ok():
        return None
    try:
        return s3.presigned_get(storage_key, filename=name)
    except Exception:  # noqa: BLE001 — o player cai no stream autenticado
        return None


def _file_info(
    row_id: str,
    name: str | None,
    size: int | None,
    mtime: datetime,
    storage_key: str | None,
    thumb_key: str | None,
    play_url: str | None = None,
) -> FileInfo | None:
    if not name or not storage_key:
        return None
    # thumb_url fica None de propósito: a grade usa /api/media/thumb (URL estável/cacheável).
    thumb = Path(name).with_suffix(".jpg").name if thumb_key else None
    return FileInfo(
        id=row_id,
        name=name,
        size=int(size or 0),
        mtime=_mtime(mtime),
        thumb=thumb,
        play_url=play_url,
        thumb_url=None,
    )


def _file_infos_from_rows(rows) -> list[FileInfo]:
    if not rows:
        return []
    play_urls: list[str | None]
    if s3.playback_cors_ok():
        pairs = [(row.storage_key, row.filename) for row in rows]
        play_urls = list(_PRESIGN_POOL.map(lambda pair: _try_presign_play(*pair), pairs))
    else:
        play_urls = [None] * len(rows)
    files: list[FileInfo] = []
    for row, play_url in zip(rows, play_urls, strict=True):
        info = _file_info(
            row.id,
            row.filename,
            row.tamanho_bytes,
            row.criado_em,
            row.storage_key,
            row.thumb_key,
            play_url,
        )
        if info:
            files.append(info)
    return files


def list_library_files(
    db: Session,
    usuario_id: str,
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
) -> tuple[list[FileInfo], PaginationMeta]:
    query = (
        db.query(Download)
        .filter(
            Download.usuario_id == usuario_id,
            Download.status == JobStatus.done,
            Download.filename.isnot(None),
            Download.storage_key.isnot(None),
        )
        .order_by(Download.criado_em.desc())
    )
    rows, meta = paginate_query(query, page, per_page)
    return _file_infos_from_rows(rows), meta


def get_download_by_id(db: Session, download_id: str, usuario_id: str) -> Download | None:
    return (
        db.query(Download)
        .options(selectinload(Download.cortes))
        .filter(Download.id == download_id, Download.usuario_id == usuario_id)
        .one_or_none()
    )


def get_corte_by_id(db: Session, corte_id: str, usuario_id: str) -> Corte | None:
    return (
        db.query(Corte)
        .filter(Corte.id == corte_id, Corte.usuario_id == usuario_id)
        .one_or_none()
    )


def list_library_cortes(db: Session, download_id: str, usuario_id: str) -> list[FileInfo]:
    download = get_download_by_id(db, download_id, usuario_id)
    files: list[FileInfo] = []
    if download:
        cortes = (
            db.query(Corte)
            .filter(
                Corte.download_id == download.id,
                Corte.status == JobStatus.done,
                Corte.filename.isnot(None),
                Corte.storage_key.isnot(None),
            )
            .order_by(Corte.criado_em.desc())
            .all()
        )
        files.extend(_file_infos_from_rows(cortes))
    return files


def get_downloads_by_filename(db: Session, filename: str, usuario_id: str) -> list[Download]:
    return (
        db.query(Download)
        .options(selectinload(Download.cortes))
        .filter(Download.usuario_id == usuario_id, Download.filename == filename)
        .order_by(Download.criado_em.desc())
        .all()
    )


def get_download_by_filename(db: Session, filename: str, usuario_id: str) -> Download | None:
    rows = get_downloads_by_filename(db, filename, usuario_id)
    return rows[0] if rows else None


def get_cortes_by_filename(db: Session, filename: str, usuario_id: str) -> list[Corte]:
    return (
        db.query(Corte)
        .filter(Corte.usuario_id == usuario_id, Corte.filename == filename)
        .order_by(Corte.criado_em.desc())
        .all()
    )


def get_corte_by_filename(db: Session, filename: str, usuario_id: str) -> Corte | None:
    rows = get_cortes_by_filename(db, filename, usuario_id)
    return rows[0] if rows else None


def get_media_row(db: Session, media_id: str, folder: str, usuario_id: str):
    if folder == "downloads":
        return get_download_by_id(db, media_id, usuario_id)
    if folder == "cortes":
        return get_corte_by_id(db, media_id, usuario_id)
    return None


def library_media_info(db: Session, media_id: str, folder: str, usuario_id: str) -> MediaInfo | None:
    if folder == "downloads":
        row = get_download_by_id(db, media_id, usuario_id)
        if not row or not row.filename or not row.storage_key:
            return None
        return MediaInfo(
            name=row.filename,
            duration=float(row.duracao_seg or 0),
            width=row.largura,
            height=row.altura,
            size=int(row.tamanho_bytes or 0),
        )
    row = get_corte_by_id(db, media_id, usuario_id)
    if not row or not row.filename or not row.storage_key:
        return None
    duration = float((row.fim_seg or 0) - (row.inicio_seg or 0))
    parent = db.get(Download, row.download_id)
    return MediaInfo(
        name=row.filename,
        duration=duration if duration > 0 else float(parent.duracao_seg or 0) if parent else 0,
        width=parent.largura if parent else None,
        height=parent.altura if parent else None,
        size=int(row.tamanho_bytes or 0),
    )


def storage_keys_for(
    db: Session, media_id: str, folder: str, usuario_id: str
) -> tuple[str | None, str | None, str | None]:
    row = get_media_row(db, media_id, folder, usuario_id)
    if not row:
        return None, None, None
    return row.storage_key, row.thumb_key, row.filename


def delete_library_media(media_id: str, folder: str, usuario_id: str) -> tuple[str, int]:
    """Remove objetos no MinIO e linhas no MySQL. Não toca em data/."""
    db = SessionLocal()
    try:
        if folder == "cortes":
            corte = get_corte_by_id(db, media_id, usuario_id)
            if not corte:
                raise HTTPException(status_code=404, detail="Arquivo não encontrado")
            name = corte.filename or media_id
            s3.remove_object(corte.storage_key)
            s3.remove_object(corte.thumb_key)
            db.delete(corte)
            db.commit()
            return name, 0

        if folder != "downloads":
            raise HTTPException(status_code=400, detail="Pasta inválida")

        download = get_download_by_id(db, media_id, usuario_id)
        if not download:
            raise HTTPException(status_code=404, detail="Arquivo não encontrado")

        name = download.filename or media_id
        cortes_deleted = 0
        for corte in list(download.cortes):
            s3.remove_object(corte.storage_key)
            s3.remove_object(corte.thumb_key)
            db.delete(corte)
            cortes_deleted += 1
        s3.remove_object(download.storage_key)
        s3.remove_object(download.thumb_key)
        db.delete(download)
        db.commit()
        return name, cortes_deleted
    finally:
        db.close()
