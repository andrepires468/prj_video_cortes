from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.db import SessionLocal
from app.models.orm import Corte, Download
from app.models.schemas import FileInfo, JobStatus, MediaInfo
from app.services import s3


def _mtime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _file_info(
    name: str | None,
    size: int | None,
    mtime: datetime,
    storage_key: str | None,
    thumb_key: str | None,
) -> FileInfo | None:
    if not name or not storage_key:
        return None
    play_url = None
    thumb_url = None
    if thumb_key:
        try:
            thumb_url = s3.presigned_get(thumb_key, filename=Path(name).with_suffix(".jpg").name)
        except Exception:  # noqa: BLE001 — a grade cai no stream autenticado
            thumb_url = None
    if s3.playback_cors_ok():
        try:
            play_url = s3.presigned_get(storage_key, filename=name)
        except Exception:  # noqa: BLE001 — o player cai no stream autenticado
            play_url = None
    thumb = Path(name).with_suffix(".jpg").name if thumb_key else None
    return FileInfo(
        name=name,
        size=int(size or 0),
        mtime=_mtime(mtime),
        thumb=thumb,
        play_url=play_url,
        thumb_url=thumb_url,
    )


def list_library_files(db: Session, usuario_id: str) -> list[FileInfo]:
    rows = (
        db.query(Download)
        .filter(
            Download.usuario_id == usuario_id,
            Download.status == JobStatus.done,
            Download.filename.isnot(None),
            Download.storage_key.isnot(None),
        )
        .order_by(Download.criado_em.desc())
        .all()
    )
    files: list[FileInfo] = []
    for row in rows:
        info = _file_info(row.filename, row.tamanho_bytes, row.criado_em, row.storage_key, row.thumb_key)
        if info:
            files.append(info)
    return files


def list_library_cortes(db: Session, source_filename: str, usuario_id: str) -> list[FileInfo]:
    download = (
        db.query(Download)
        .filter(Download.usuario_id == usuario_id, Download.filename == source_filename)
        .one_or_none()
    )
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
        for row in cortes:
            info = _file_info(row.filename, row.tamanho_bytes, row.criado_em, row.storage_key, row.thumb_key)
            if info:
                files.append(info)
    return files


def get_download_by_filename(db: Session, filename: str, usuario_id: str) -> Download | None:
    return (
        db.query(Download)
        .options(selectinload(Download.cortes))
        .filter(Download.usuario_id == usuario_id, Download.filename == filename)
        .one_or_none()
    )


def get_corte_by_filename(db: Session, filename: str, usuario_id: str) -> Corte | None:
    return (
        db.query(Corte)
        .filter(Corte.usuario_id == usuario_id, Corte.filename == filename)
        .one_or_none()
    )


def library_media_info(db: Session, filename: str, folder: str, usuario_id: str) -> MediaInfo | None:
    if folder == "downloads":
        row = get_download_by_filename(db, filename, usuario_id)
        if not row or not row.filename or not row.storage_key:
            return None
        return MediaInfo(
            name=row.filename,
            duration=float(row.duracao_seg or 0),
            width=row.largura,
            height=row.altura,
            size=int(row.tamanho_bytes or 0),
        )
    row = get_corte_by_filename(db, filename, usuario_id)
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


def storage_keys_for(db: Session, filename: str, folder: str, usuario_id: str) -> tuple[str | None, str | None]:
    if folder == "downloads":
        row = get_download_by_filename(db, filename, usuario_id)
        if not row:
            return None, None
        return row.storage_key, row.thumb_key
    row = get_corte_by_filename(db, filename, usuario_id)
    if not row:
        return None, None
    return row.storage_key, row.thumb_key


def delete_library_media(filename: str, folder: str, usuario_id: str) -> tuple[str, int]:
    """Remove objetos no MinIO e linhas no MySQL. Não toca em data/."""
    db = SessionLocal()
    try:
        if folder == "cortes":
            corte = get_corte_by_filename(db, filename, usuario_id)
            if not corte:
                raise HTTPException(status_code=404, detail="Arquivo não encontrado")
            s3.remove_object(corte.storage_key)
            s3.remove_object(corte.thumb_key)
            db.delete(corte)
            db.commit()
            return filename, 0

        if folder != "downloads":
            raise HTTPException(status_code=400, detail="Pasta inválida")

        download = get_download_by_filename(db, filename, usuario_id)
        if not download:
            raise HTTPException(status_code=404, detail="Arquivo não encontrado")

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
        return filename, cortes_deleted
    finally:
        db.close()
