from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    error = "error"


class DownloadRequest(BaseModel):
    url: str = Field(..., min_length=8, description="URL do vídeo (YouTube, X, TikTok ou Instagram)")


class JobCreated(BaseModel):
    id: str
    status: JobStatus


class JobInfo(BaseModel):
    id: str
    status: JobStatus
    progress: float = 0.0
    message: str = ""
    url: str = ""
    filename: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class FileInfo(BaseModel):
    name: str
    size: int
    mtime: datetime
    thumb: Optional[str] = None


class FileListResponse(BaseModel):
    files: list[FileInfo]


class DeleteMediaResponse(BaseModel):
    deleted: str
    cortes_deleted: int = 0


class HealthResponse(BaseModel):
    status: str = "ok"


class MediaInfo(BaseModel):
    name: str
    duration: float
    width: Optional[int] = None
    height: Optional[int] = None
    size: int


class CutSegment(BaseModel):
    start: float = Field(..., ge=0)
    end: float = Field(..., gt=0)


class CutRequest(BaseModel):
    filename: str = Field(..., min_length=1)
    source_filename: Optional[str] = Field(
        default=None,
        description="Corte em data/cortes a usar como origem; o arquivo gerado continua ligado ao vídeo original",
    )
    markers: list[float] = Field(default_factory=list)
    segments: list[CutSegment] | None = None
    speed: float = Field(1.0, ge=0.25, le=2.0, description="Velocidade do corte gerado (0.25–2.0)")


class CutJobInfo(BaseModel):
    id: str
    status: JobStatus
    progress: float = 0.0
    message: str = ""
    filename: str = ""
    outputs: list[str] = Field(default_factory=list)
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
