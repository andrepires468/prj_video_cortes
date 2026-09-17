from __future__ import annotations

import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.db import SessionLocal
from app.models.orm import Download
from app.models.schemas import JobInfo, JobStatus
from app.providers.registry import get_provider
from app.services import s3
from app.services.probe import ensure_faststart, probe_media
from app.services.thumbnail import generate_thumbnail_to

_lock = threading.Lock()
_TERMINAL = {JobStatus.done, JobStatus.error, JobStatus.cancelled}


class JobCancelled(Exception):
    """Sinaliza que o usuário pediu para abortar o job."""


@dataclass
class _JobRuntime:
    cancel: threading.Event = field(default_factory=threading.Event)
    stage: str = "download"
    download_progress: float = 0.0
    upload_progress: float = 0.0
    work_dir: Path | None = None
    storage_keys: list[str] = field(default_factory=list)
    last_db_write: float = 0.0


_runtime: dict[str, _JobRuntime] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _provider_label(provider: object) -> str:
    return provider.__class__.__name__.removesuffix("Provider").lower()[:32]


def _work_dir(usuario_id: str, job_id: str) -> Path:
    return Path(settings.downloads_dir) / usuario_id / job_id


def _runtime_for(job_id: str) -> _JobRuntime:
    with _lock:
        rt = _runtime.get(job_id)
        if rt is None:
            rt = _JobRuntime()
            _runtime[job_id] = rt
        return rt


def _drop_runtime(job_id: str) -> None:
    with _lock:
        _runtime.pop(job_id, None)


def _is_cancelled(job_id: str) -> bool:
    rt = _runtime.get(job_id)
    return bool(rt and rt.cancel.is_set())


def _ensure_not_cancelled(job_id: str) -> None:
    if _is_cancelled(job_id):
        raise JobCancelled()


def _cleanup_local(work: Path | None) -> None:
    if work is None:
        return
    shutil.rmtree(work, ignore_errors=True)
    parent = work.parent
    try:
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
    except OSError:
        return


def _cleanup_storage(keys: list[str] | None) -> None:
    for key in keys or []:
        s3.remove_object(key)


def _to_job_info(row: Download) -> JobInfo:
    rt = _runtime.get(row.id)
    stage = "download"
    download_progress = 0.0
    upload_progress = 0.0
    if row.status == JobStatus.done:
        stage = "upload"
        download_progress = 100.0
        upload_progress = 100.0
    elif rt:
        stage = rt.stage
        download_progress = rt.download_progress
        upload_progress = rt.upload_progress
        if rt.stage == "upload":
            download_progress = max(download_progress, 100.0)
    elif row.status == JobStatus.running:
        message = (row.mensagem or "").lower()
        pct = float(row.progress or 0)
        upload_hints = ("storage", "upload", "banco", "thumbnail", "otimiz", "enviando", "gravando")
        if any(hint in message for hint in upload_hints):
            stage = "upload"
            download_progress = 100.0
            upload_progress = pct
        else:
            download_progress = pct
    elif row.status == JobStatus.cancelled:
        pct = float(row.progress or 0)
        message = (row.mensagem or "").lower()
        if "upload" in message or "storage" in message or "banco" in message:
            stage = "upload"
            download_progress = 100.0
            upload_progress = pct
        else:
            download_progress = pct

    overall = round((download_progress + upload_progress) / 2.0, 1)
    return JobInfo(
        id=row.id,
        status=row.status,
        progress=overall,
        message=row.mensagem or "",
        url=row.url_origem,
        filename=row.filename,
        error=row.erro,
        created_at=row.criado_em,
        updated_at=row.atualizado_em,
        stage=stage,
        download_progress=round(min(download_progress, 100.0), 1),
        upload_progress=round(min(upload_progress, 100.0), 1),
    )


def create_job(url: str, usuario_id: str) -> JobInfo:
    provider = get_provider(url)
    job_id = str(uuid.uuid4())
    now = _now()
    _runtime_for(job_id)
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


def _update_job(job_id: str, *, force: bool = True, **kwargs) -> None:
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
            incoming_status = kwargs.get("status")
            if row.status == JobStatus.cancelled and incoming_status != JobStatus.cancelled:
                return
            if row.status in _TERMINAL and incoming_status is None:
                return
            for key, value in kwargs.items():
                attr = field_map.get(key)
                if attr:
                    setattr(row, attr, value)
            row.atualizado_em = _now()
            db.commit()
        finally:
            db.close()
            if force:
                rt = _runtime.get(job_id)
                if rt:
                    rt.last_db_write = time.monotonic()


def _set_stage_progress(
    job_id: str,
    stage: str,
    pct: float,
    message: str,
    *,
    filename: str | None = None,
    force: bool = False,
) -> None:
    _ensure_not_cancelled(job_id)
    pct = round(min(max(pct, 0.0), 100.0), 1)
    now = time.monotonic()
    rt = _runtime_for(job_id)
    with _lock:
        rt.stage = stage
        if stage == "download":
            rt.download_progress = pct
        else:
            rt.download_progress = 100.0
            rt.upload_progress = pct
        due = force or (now - rt.last_db_write) >= 0.35
    if not due:
        return
    payload = {"progress": pct, "message": message}
    if filename:
        payload["filename"] = filename
    _update_job(job_id, **payload)


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


def _mark_cancelled(job_id: str) -> None:
    _update_job(
        job_id,
        status=JobStatus.cancelled,
        message="Processo cancelado",
        error=None,
        storage_key=None,
        thumb_key=None,
        force=True,
    )


def cancel_job(job_id: str, usuario_id: str) -> JobInfo | None:
    db = SessionLocal()
    try:
        row = (
            db.query(Download)
            .filter(Download.id == job_id, Download.usuario_id == usuario_id)
            .one_or_none()
        )
        if not row:
            return None
        current = _to_job_info(row)
        if row.status in {JobStatus.done, JobStatus.cancelled, JobStatus.error}:
            return current
        rt = _runtime_for(job_id)
        rt.cancel.set()
        keys = list(rt.storage_keys)
        work = rt.work_dir
        pct = rt.upload_progress if rt.stage == "upload" else rt.download_progress
        row.status = JobStatus.cancelled
        row.progress = pct
        row.mensagem = "Processo cancelado"
        row.erro = None
        row.storage_key = None
        row.thumb_key = None
        row.atualizado_em = _now()
        db.commit()
        db.refresh(row)
        info = _to_job_info(row)
    finally:
        db.close()

    _cleanup_storage(keys)
    _cleanup_local(work)
    return info


def _finalize_cancel(job_id: str, work: Path | None, keys: list[str]) -> None:
    _cleanup_storage(keys)
    _cleanup_local(work)
    _mark_cancelled(job_id)


def run_download(job_id: str) -> None:
    db = SessionLocal()
    try:
        row = db.get(Download, job_id)
        if not row:
            return
        url = row.url_origem
        usuario_id = row.usuario_id
        if row.status == JobStatus.cancelled:
            return
    finally:
        db.close()

    rt = _runtime_for(job_id)
    if rt.cancel.is_set():
        _finalize_cancel(job_id, rt.work_dir, list(rt.storage_keys))
        return

    _update_job(
        job_id,
        status=JobStatus.running,
        message="Iniciando download…",
        progress=0.0,
        force=True,
    )

    def download_cb(pct: float, message: str) -> None:
        _set_stage_progress(job_id, "download", min(pct, 99.0), message)

    work = _work_dir(usuario_id, job_id)
    rt.work_dir = work
    storage_key = None
    thumb_key = None
    try:
        work.mkdir(parents=True, exist_ok=True)
        _ensure_not_cancelled(job_id)
        provider = get_provider(url)
        path = provider.download(url, work, download_cb)
        _ensure_not_cancelled(job_id)
        final_name = _unique_filename(usuario_id, path.name, job_id)
        if final_name != path.name:
            renamed = path.with_name(final_name)
            path = path.rename(renamed)
        _set_stage_progress(job_id, "download", 100.0, "Download local concluído", filename=path.name, force=True)

        _set_stage_progress(job_id, "upload", 2.0, "Preparando arquivo para o storage…", filename=path.name, force=True)
        path = ensure_faststart(path)
        _ensure_not_cancelled(job_id)
        _set_stage_progress(job_id, "upload", 12.0, "Gerando thumbnail…", filename=path.name, force=True)
        thumb_path = None
        try:
            thumb_path = generate_thumbnail_to(path, path.with_suffix(".jpg"))
        except Exception as thumb_exc:  # noqa: BLE001 — upload segue mesmo se thumb falhar
            _set_stage_progress(
                job_id,
                "upload",
                16.0,
                f"Thumbnail falhou; seguindo o upload: {thumb_exc}",
                filename=path.name,
                force=True,
            )

        info = None
        try:
            info = probe_media(path)
        except Exception:  # noqa: BLE001
            info = None
        _ensure_not_cancelled(job_id)

        def map_upload_pct(file_pct: float) -> float:
            return 22.0 + min(file_pct, 100.0) * 0.70

        def on_video_progress(file_pct: float) -> None:
            _set_stage_progress(
                job_id,
                "upload",
                map_upload_pct(file_pct),
                f"Enviando ao storage… {file_pct:.0f}%",
                filename=path.name,
            )

        _set_stage_progress(job_id, "upload", 22.0, "Enviando ao storage…", filename=path.name, force=True)
        storage_key = s3.download_object_key(usuario_id, job_id, path.name)
        rt.storage_keys.append(storage_key)
        s3.put_file(
            storage_key,
            path,
            on_progress=on_video_progress,
            check=lambda: _ensure_not_cancelled(job_id),
        )
        _ensure_not_cancelled(job_id)

        if thumb_path is not None and thumb_path.is_file():
            _set_stage_progress(job_id, "upload", 94.0, "Enviando thumbnail…", filename=path.name, force=True)
            thumb_key = s3.download_thumb_key(usuario_id, job_id, path.stem)
            rt.storage_keys.append(thumb_key)
            s3.put_file(thumb_key, thumb_path, check=lambda: _ensure_not_cancelled(job_id))

        _set_stage_progress(job_id, "upload", 98.0, "Gravando no banco…", filename=path.name, force=True)
        _ensure_not_cancelled(job_id)
        with _lock:
            rt.upload_progress = 100.0
            rt.download_progress = 100.0
            rt.stage = "upload"
        _update_job(
            job_id,
            status=JobStatus.done,
            progress=100.0,
            message="Download e upload concluídos",
            filename=path.name,
            storage_key=storage_key,
            thumb_key=thumb_key,
            tamanho_bytes=path.stat().st_size,
            duracao_seg=float(info.duration) if info else None,
            largura=info.width if info else None,
            altura=info.height if info else None,
            error=None,
            force=True,
        )
    except JobCancelled:
        _finalize_cancel(job_id, work, [key for key in (storage_key, thumb_key) if key])
        return
    except Exception as exc:  # noqa: BLE001 — surface any yt-dlp / IO error to UI
        if _is_cancelled(job_id):
            _finalize_cancel(job_id, work, [key for key in (storage_key, thumb_key) if key])
            return
        _cleanup_storage([key for key in (storage_key, thumb_key) if key])
        _update_job(
            job_id,
            status=JobStatus.error,
            message="Falha no download",
            error=str(exc),
            storage_key=None,
            thumb_key=None,
            force=True,
        )
    finally:
        _cleanup_local(work)
        _drop_runtime(job_id)
