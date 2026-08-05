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
    url: str = Field(..., min_length=8, description="URL do vídeo (YouTube ou X/Twitter)")


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
    markers: list[float] = Field(default_factory=list)
    segments: list[CutSegment] | None = None


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
