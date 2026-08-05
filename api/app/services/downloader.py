from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from app.models.schemas import JobInfo, JobStatus
from app.providers.registry import get_provider
from app.services.storage import ensure_downloads_dir
from app.services.thumbnail import generate_thumbnail

_lock = threading.Lock()
_jobs: dict[str, JobInfo] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_job(url: str) -> JobInfo:
    # Validate provider early
    get_provider(url)
    job_id = str(uuid.uuid4())
    job = JobInfo(
        id=job_id,
        status=JobStatus.queued,
        progress=0.0,
        message="Na fila",
        url=url,
        created_at=_now(),
        updated_at=_now(),
    )
    with _lock:
        _jobs[job_id] = job
    return job


def get_job(job_id: str) -> JobInfo | None:
    with _lock:
        return _jobs.get(job_id)


def _update_job(job_id: str, **kwargs) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        data = job.model_dump()
        data.update(kwargs)
        data["updated_at"] = _now()
        _jobs[job_id] = JobInfo(**data)


def run_download(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return

    _update_job(
        job_id,
        status=JobStatus.running,
        message="Iniciando download…",
        progress=0.0,
    )

    def progress_cb(pct: float, message: str) -> None:
        _update_job(job_id, progress=round(pct, 1), message=message)

    try:
        provider = get_provider(job.url)
        dest = ensure_downloads_dir()
        path = provider.download(job.url, dest, progress_cb)

        _update_job(job_id, message="Gerando thumbnail…", progress=98.0)
        try:
            generate_thumbnail(path)
        except Exception as thumb_exc:  # noqa: BLE001 — download ok mesmo se thumb falhar
            _update_job(
                job_id,
                message=f"Download ok; thumbnail falhou: {thumb_exc}",
            )

        _update_job(
            job_id,
            status=JobStatus.done,
            progress=100.0,
            message="Download concluído",
            filename=path.name,
            error=None,
        )
    except Exception as exc:  # noqa: BLE001 — surface any yt-dlp / IO error to UI
        _update_job(
            job_id,
            status=JobStatus.error,
            message="Falha no download",
            error=str(exc),
        )
