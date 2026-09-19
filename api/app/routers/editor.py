from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import SessionLocal
from app.models.orm import Usuario
from app.models.pagination import pagination_for_items
from app.models.schemas import CutJobInfo, CutRequest, FileListResponse, JobCreated, JobStatus
from app.services import cutter, library
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/editor", tags=["editor"], dependencies=[Depends(get_current_user)])


@router.get("/cortes", response_model=FileListResponse)
def list_video_cortes(
    id: str = Query(..., min_length=1, description="ID do download"),
    usuario: Usuario = Depends(get_current_user),
) -> FileListResponse:
    db = SessionLocal()
    try:
        in_db = library.get_download_by_id(db, id, usuario.id)
        if not in_db or not in_db.storage_key:
            raise HTTPException(status_code=404, detail="Arquivo não encontrado")
        cortes = library.list_library_cortes(db, id, usuario.id)
        return FileListResponse(files=cortes, pagination=pagination_for_items(cortes))
    finally:
        db.close()


@router.post("/cuts", response_model=JobCreated)
def start_cuts(
    body: CutRequest,
    usuario: Usuario = Depends(get_current_user),
) -> JobCreated:
    try:
        job = cutter.create_cut_job(
            download_id=body.download_id,
            markers=body.markers,
            usuario_id=usuario.id,
            segments=body.segments,
            speed=body.speed,
            source_corte_id=body.source_corte_id,
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
