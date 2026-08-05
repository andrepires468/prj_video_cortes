from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import CutJobInfo, CutRequest, JobCreated, JobStatus
from app.services import cutter

router = APIRouter(prefix="/api/editor", tags=["editor"])


@router.post("/cuts", response_model=JobCreated)
def start_cuts(body: CutRequest) -> JobCreated:
    try:
        job = cutter.create_cut_job(
            filename=body.filename,
            markers=body.markers,
            segments=body.segments,
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
