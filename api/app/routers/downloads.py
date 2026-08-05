from __future__ import annotations

import threading

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    DownloadRequest,
    FileListResponse,
    JobCreated,
    JobInfo,
    JobStatus,
)
from app.services import downloader
from app.services.storage import list_files

router = APIRouter(prefix="/api/downloads", tags=["downloads"])


@router.post("", response_model=JobCreated)
def start_download(body: DownloadRequest) -> JobCreated:
    try:
        job = downloader.create_job(body.url.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Run in a dedicated thread so progress updates are not blocked by sync yt-dlp
    def _run() -> None:
        downloader.run_download(job.id)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return JobCreated(id=job.id, status=JobStatus.queued)


@router.get("/jobs/{job_id}", response_model=JobInfo)
def job_status(job_id: str) -> JobInfo:
    job = downloader.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return job


@router.get("/files", response_model=FileListResponse)
def files() -> FileListResponse:
    return FileListResponse(files=list_files())
