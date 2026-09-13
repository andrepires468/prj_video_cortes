from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse

from app.db import SessionLocal
from app.models.orm import Usuario
from app.models.schemas import DeleteMediaResponse, MediaInfo
from app.services import library, s3
from app.services.auth import get_current_user
from app.services.probe import probe_media
from app.services.storage import is_image_file, is_video_file, resolve_media_file
from app.services.thumbnail import generate_thumbnail, thumbnail_path_for

router = APIRouter(prefix="/api/media", tags=["media"], dependencies=[Depends(get_current_user)])

FolderKind = Literal["downloads", "cortes"]

_MEDIA_TYPES = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".m4v": "video/x-m4v",
}


def _parse_range(header: str | None, size: int) -> tuple[int, int] | None:
    if not header or not header.startswith("bytes="):
        return None
    spec = header.removeprefix("bytes=").split(",")[0].strip()
    if "-" not in spec:
        return None
    start_s, end_s = spec.split("-", 1)
    try:
        if start_s == "":
            length = int(end_s)
            start = max(size - length, 0)
            end = size - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s else size - 1
    except ValueError:
        return None
    if start < 0 or start >= size:
        return None
    end = min(end, size - 1)
    if end < start:
        return None
    return start, end


def _stream_s3(key: str, filename: str, media_type: str, download: bool, request: Request):
    stat = s3.stat_object(key)
    size = int(stat.size or 0)
    range_pair = _parse_range(request.headers.get("range"), size) if size else None
    if range_pair:
        start, end = range_pair
        length = end - start + 1
        obj = s3.get_object(key, offset=start, length=length)
        status = 206
        extra = {"Content-Range": f"bytes {start}-{end}/{size}", "Content-Length": str(length)}
    else:
        obj = s3.get_object(key)
        status = 200
        extra = {"Content-Length": str(size)} if size else {}

    disposition = "attachment" if download else "inline"

    def chunks():
        try:
            while True:
                data = obj.read(64 * 1024)
                if not data:
                    break
                yield data
        finally:
            obj.close()
            obj.release_conn()

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'{disposition}; filename="{filename}"',
        **extra,
    }
    return StreamingResponse(chunks(), status_code=status, media_type=media_type, headers=headers)


@router.get("/info", response_model=MediaInfo)
def media_info(
    name: str = Query(..., min_length=1),
    folder: FolderKind = Query("downloads"),
    usuario: Usuario = Depends(get_current_user),
) -> MediaInfo:
    from_db = None
    db = SessionLocal()
    try:
        from_db = library.library_media_info(db, name, folder, usuario.id)
        if from_db and from_db.duration > 0:
            return from_db
    finally:
        db.close()
    try:
        path = resolve_media_file(name, folder)
    except HTTPException:
        if from_db:
            return from_db
        raise
    if not is_video_file(path):
        raise HTTPException(status_code=400, detail="Arquivo não é um vídeo suportado")
    try:
        return probe_media(path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/stream")
def media_stream(
    request: Request,
    name: str = Query(..., min_length=1),
    folder: FolderKind = Query("downloads"),
    download: bool = Query(False),
    usuario: Usuario = Depends(get_current_user),
):
    try:
        path = resolve_media_file(name, folder)
        if is_video_file(path) and library.allow_disk_fallback(usuario.id):
            media_type = _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
            return FileResponse(
                path,
                media_type=media_type,
                filename=path.name,
                content_disposition_type="attachment" if download else "inline",
            )
    except HTTPException:
        pass

    db = SessionLocal()
    storage_key = None
    try:
        storage_key, _ = library.storage_keys_for(db, name, folder, usuario.id)
    finally:
        db.close()

    if storage_key:
        try:
            media_type = s3.content_type_for(name)
            return _stream_s3(storage_key, Path(name).name, media_type, download, request)
        except Exception as exc:
            raise HTTPException(status_code=404, detail="Arquivo não encontrado") from exc

    raise HTTPException(status_code=404, detail="Arquivo não encontrado")


@router.get("/thumb")
def media_thumb(
    request: Request,
    name: str = Query(..., min_length=1),
    folder: FolderKind = Query("downloads"),
    usuario: Usuario = Depends(get_current_user),
):
    try:
        path = resolve_media_file(name, folder)
        if is_image_file(path) and library.allow_disk_fallback(usuario.id):
            return FileResponse(
                path,
                media_type="image/jpeg",
                filename=path.name,
                content_disposition_type="inline",
            )
        if is_video_file(path) and library.allow_disk_fallback(usuario.id):
            thumb = thumbnail_path_for(path)
            if not thumb.is_file():
                try:
                    thumb = generate_thumbnail(path)
                except Exception:
                    thumb = None
            if thumb is not None and thumb.is_file():
                return FileResponse(
                    thumb,
                    media_type="image/jpeg",
                    filename=thumb.name,
                    content_disposition_type="inline",
                )
    except HTTPException:
        pass

    db = SessionLocal()
    thumb_key = None
    try:
        _, thumb_key = library.storage_keys_for(db, name, folder, usuario.id)
    finally:
        db.close()

    if thumb_key:
        try:
            return _stream_s3(thumb_key, Path(name).with_suffix(".jpg").name, "image/jpeg", False, request)
        except Exception as exc:
            raise HTTPException(status_code=404, detail="Thumbnail não encontrada") from exc

    raise HTTPException(status_code=404, detail="Thumbnail não encontrada")


@router.delete("", response_model=DeleteMediaResponse)
def media_delete(
    name: str = Query(..., min_length=1),
    folder: FolderKind = Query("downloads"),
    usuario: Usuario = Depends(get_current_user),
) -> DeleteMediaResponse:
    deleted, cortes_deleted = library.delete_library_media(name, folder, usuario.id)
    return DeleteMediaResponse(deleted=deleted, cortes_deleted=cortes_deleted)
