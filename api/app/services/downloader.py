from __future__ import annotations

import shutil
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.db import SessionLocal
from app.models.orm import Download
from app.models.schemas import JobInfo, JobStatus
from app.providers.registry import get_provider
from app.services import s3
from app.services.probe import ensure_faststart, probe_media
from app.services.thumbnail import generate_thumbnail_to

_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _provider_label(provider: object) -> str:
    return provider.__class__.__name__.removesuffix("Provider").lower()[:32]


def _to_job_info(row: Download) -> JobInfo:
    return JobInfo(
        id=row.id,
        status=row.status,
        progress=float(row.progress or 0),
        message=row.mensagem or "",
        url=row.url_origem,
        filename=row.filename,
        error=row.erro,
        created_at=row.criado_em,
        updated_at=row.atualizado_em,
    )


def create_job(url: str, usuario_id: str) -> JobInfo:
    provider = get_provider(url)
    job_id = str(uuid.uuid4())
    now = _now()
    db = SessionLocal()
    try:
        row = Download(
            id=job_id,
            usuario_id=usuario_id,
            url_origem=url[:2048],
            provider=_provider_label(provider),
            status=JobStatus.queued,
            progress=0.0,
            mensagem="Na fila",
            criado_em=now,
            atualizado_em=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _to_job_info(row)
    finally:
        db.close()


def get_job(job_id: str, usuario_id: str) -> JobInfo | None:
    db = SessionLocal()
    try:
        row = (
            db.query(Download)
            .filter(Download.id == job_id, Download.usuario_id == usuario_id)
            .one_or_none()
        )
        return _to_job_info(row) if row else None
    finally:
        db.close()


def _update_job(job_id: str, **kwargs) -> None:
    field_map = {
        "status": "status",
        "progress": "progress",
        "message": "mensagem",
        "filename": "filename",
        "error": "erro",
        "storage_key": "storage_key",
        "thumb_key": "thumb_key",
        "tamanho_bytes": "tamanho_bytes",
        "duracao_seg": "duracao_seg",
        "largura": "largura",
        "altura": "altura",
        "provider": "provider",
    }
    with _lock:
        db = SessionLocal()
        try:
            row = db.get(Download, job_id)
            if not row:
                return
            for key, value in kwargs.items():
                attr = field_map.get(key)
                if attr:
                    setattr(row, attr, value)
            row.atualizado_em = _now()
            db.commit()
        finally:
            db.close()


def _unique_filename(usuario_id: str, filename: str, job_id: str) -> str:
    db = SessionLocal()
    try:
        clash = (
            db.query(Download.id)
            .filter(
                Download.usuario_id == usuario_id,
                Download.filename == filename,
                Download.id != job_id,
            )
            .first()
        )
    finally:
        db.close()
    if not clash:
        return filename
    path = Path(filename)
    return f"{path.stem}_{job_id[:8]}{path.suffix}"[:255]


def run_download(job_id: str) -> None:
    db = SessionLocal()
    try:
        row = db.get(Download, job_id)
        if not row:
            return
        url = row.url_origem
        usuario_id = row.usuario_id
    finally:
        db.close()

    _update_job(
        job_id,
        status=JobStatus.running,
        message="Iniciando download…",
        progress=0.0,
    )

    def progress_cb(pct: float, message: str) -> None:
        _update_job(job_id, progress=round(min(pct, 88.0), 1), message=message)

    work = Path(tempfile.mkdtemp(prefix="vc-dl-"))
    storage_key = None
    thumb_key = None
    try:
        provider = get_provider(url)
        path = provider.download(url, work, progress_cb)
        final_name = _unique_filename(usuario_id, path.name, job_id)
        if final_name != path.name:
            renamed = path.with_name(final_name)
            path = path.rename(renamed)

        _update_job(job_id, message="Otimizando para reprodução…", progress=89.0, filename=path.name)
        path = ensure_faststart(path)

        _update_job(job_id, message="Gerando thumbnail…", progress=90.0, filename=path.name)
        thumb_path = None
        try:
            thumb_path = generate_thumbnail_to(path, path.with_suffix(".jpg"))
        except Exception as thumb_exc:  # noqa: BLE001 — download ok mesmo se thumb falhar
            _update_job(job_id, message=f"Download ok; thumbnail falhou: {thumb_exc}")

        info = None
        try:
            info = probe_media(path)
        except Exception:  # noqa: BLE001
            info = None

        _update_job(job_id, message="Enviando ao storage…", progress=94.0)
        storage_key = s3.download_object_key(usuario_id, job_id, path.name)
        s3.put_file(storage_key, path)
        if thumb_path is not None and thumb_path.is_file():
            thumb_key = s3.download_thumb_key(usuario_id, job_id, path.stem)
            s3.put_file(thumb_key, thumb_path)

        _update_job(
            job_id,
            status=JobStatus.done,
            progress=100.0,
            message="Download concluído",
            filename=path.name,
            storage_key=storage_key,
            thumb_key=thumb_key,
            tamanho_bytes=path.stat().st_size,
            duracao_seg=float(info.duration) if info else None,
            largura=info.width if info else None,
            altura=info.height if info else None,
            error=None,
        )
    except Exception as exc:  # noqa: BLE001 — surface any yt-dlp / IO error to UI
        s3.remove_object(storage_key)
        s3.remove_object(thumb_key)
        _update_job(
            job_id,
            status=JobStatus.error,
            message="Falha no download",
            error=str(exc),
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)
