from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.models.schemas import MediaInfo
from app.services.probe import probe_media
from app.services.storage import is_image_file, is_video_file, resolve_download_file
from app.services.thumbnail import thumbnail_path_for

router = APIRouter(prefix="/api/media", tags=["media"])


@router.get("/info", response_model=MediaInfo)
def media_info(name: str = Query(..., min_length=1)) -> MediaInfo:
    path = resolve_download_file(name)
    if not is_video_file(path):
        raise HTTPException(status_code=400, detail="Arquivo não é um vídeo suportado")
    try:
        return probe_media(path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/stream")
def media_stream(name: str = Query(..., min_length=1)) -> FileResponse:
    path = resolve_download_file(name)
    if not is_video_file(path):
        raise HTTPException(status_code=400, detail="Arquivo não é um vídeo suportado")

    media_types = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".m4v": "video/x-m4v",
    }
    media_type = media_types.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(
        path,
        media_type=media_type,
        filename=path.name,
        content_disposition_type="inline",
    )


@router.get("/thumb")
def media_thumb(name: str = Query(..., min_length=1)) -> FileResponse:
    """Serve a thumbnail do vídeo (mesmo stem .jpg) ou o próprio arquivo se já for imagem."""
    path = resolve_download_file(name)
    if is_image_file(path):
        thumb = path
    elif is_video_file(path):
        thumb = thumbnail_path_for(path)
        if not thumb.is_file():
            raise HTTPException(status_code=404, detail="Thumbnail não encontrada")
    else:
        raise HTTPException(status_code=400, detail="Arquivo não suportado para thumbnail")

    return FileResponse(
        thumb,
        media_type="image/jpeg",
        filename=thumb.name,
        content_disposition_type="inline",
    )
