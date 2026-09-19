from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.models.pagination import PaginationMeta


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    error = "error"
    cancelled = "cancelled"


class DownloadRequest(BaseModel):
    url: str = Field(..., min_length=8, description="URL do vídeo (YouTube, X, TikTok, Instagram ou Angel)")


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
    stage: str = "download"
    download_progress: float = 0.0
    upload_progress: float = 0.0


class FileInfo(BaseModel):
    name: str
    size: int
    mtime: datetime
    thumb: Optional[str] = None
    play_url: Optional[str] = None
    thumb_url: Optional[str] = None


class FileListResponse(BaseModel):
    files: list[FileInfo]
    pagination: PaginationMeta


class DeleteMediaResponse(BaseModel):
    deleted: str
    cortes_deleted: int = 0


class HealthResponse(BaseModel):
    status: str = "ok"
    database: str = "ok"


class MediaInfo(BaseModel):
    name: str
    duration: float
    width: Optional[int] = None
    height: Optional[int] = None
    size: int


class PlaybackUrlResponse(BaseModel):
    url: str
    expires_in: int


class CutSegment(BaseModel):
    start: float = Field(..., ge=0)
    end: float = Field(..., gt=0)


class CutRequest(BaseModel):
    filename: str = Field(..., min_length=1)
    source_filename: Optional[str] = Field(
        default=None,
        description="Corte já existente a usar como origem; o arquivo gerado continua ligado ao vídeo original",
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


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    senha: str = Field(..., min_length=1, max_length=128)


class UsuarioPublic(BaseModel):
    id: str
    email: str
    nome: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioPublic
