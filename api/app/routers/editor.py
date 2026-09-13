from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import SessionLocal
from app.models.orm import Usuario
from app.models.schemas import CutJobInfo, CutRequest, FileListResponse, JobCreated, JobStatus
from app.services import cutter, library
from app.services.auth import get_current_user
from app.services.storage import resolve_download_file

router = APIRouter(prefix="/api/editor", tags=["editor"], dependencies=[Depends(get_current_user)])


@router.get("/cortes", response_model=FileListResponse)
def list_video_cortes(
    filename: str = Query(..., min_length=1),
    usuario: Usuario = Depends(get_current_user),
) -> FileListResponse:
    db = SessionLocal()
    try:
        in_db = library.get_download_by_filename(db, filename, usuario.id)
        on_disk = False
        if library.allow_disk_fallback(usuario.id):
            try:
                resolve_download_file(filename)
                on_disk = True
            except HTTPException:
                on_disk = False
        if not in_db and not on_disk:
            raise HTTPException(status_code=404, detail="Arquivo não encontrado")
        return FileListResponse(files=library.list_library_cortes(db, filename, usuario.id))
    finally:
        db.close()


@router.post("/cuts", response_model=JobCreated)
def start_cuts(body: CutRequest) -> JobCreated:
    try:
        job = cutter.create_cut_job(
            filename=body.filename,
            markers=body.markers,
            segments=body.segments,
            speed=body.speed,
            source_filename=body.source_filename,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return JobCreated(id=job.id, status=JobStatus.queued)


@router.get("/cuts/{job_id}", response_model=CutJobInfo)
def cut_status(job_id: str) -> CutJobInfo:
    job = cutter.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return job
