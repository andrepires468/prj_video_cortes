from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse

from app.db import SessionLocal
from app.models.orm import Usuario
from app.config import settings
from app.models.schemas import DeleteMediaResponse, MediaInfo, PlaybackUrlResponse
from app.services import library, s3
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/media", tags=["media"], dependencies=[Depends(get_current_user)])

FolderKind = Literal["downloads", "cortes"]


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


_THUMB_CACHE_SECONDS = 86400


def _etag_of(stat) -> str | None:
    raw = (getattr(stat, "etag", None) or "").strip()
    if not raw:
        return None
    return raw if raw.startswith('"') else f'"{raw}"'


def _stream_s3(
    key: str,
    filename: str,
    media_type: str,
    download: bool,
    request: Request,
    cache_seconds: int | None = None,
):
    stat = s3.stat_object(key)
    size = int(stat.size or 0)
    etag = _etag_of(stat)
    cache_control = (
        f"private, max-age={cache_seconds}" if cache_seconds else "private, no-store"
    )
    if cache_seconds and etag:
        if_none_match = request.headers.get("if-none-match", "")
        if etag in if_none_match:
            return Response(
                status_code=304,
                headers={"ETag": etag, "Cache-Control": cache_control},
            )

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
        "Cache-Control": cache_control,
        "X-Accel-Buffering": "no",
        **extra,
    }
    if etag:
        headers["ETag"] = etag
    return StreamingResponse(chunks(), status_code=status, media_type=media_type, headers=headers)


@router.get("/info", response_model=MediaInfo)
def media_info(
    id: str = Query(..., min_length=1),
    folder: FolderKind = Query("downloads"),
    usuario: Usuario = Depends(get_current_user),
) -> MediaInfo:
    db = SessionLocal()
    try:
        from_db = library.library_media_info(db, id, folder, usuario.id)
        storage_key, _, _ = library.storage_keys_for(db, id, folder, usuario.id)
    finally:
        db.close()
    if not from_db or not storage_key:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return from_db


@router.get("/playback", response_model=PlaybackUrlResponse)
def media_playback(
    id: str = Query(..., min_length=1),
    folder: FolderKind = Query("downloads"),
    download: bool = Query(False),
    usuario: Usuario = Depends(get_current_user),
) -> PlaybackUrlResponse:
    db = SessionLocal()
    try:
        storage_key, _, filename = library.storage_keys_for(db, id, folder, usuario.id)
    finally:
        db.close()
    key = storage_key
    if not key or not filename:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    if not s3.playback_cors_ok():
        query = urlencode({"id": id, "folder": folder})
        if download:
            query += "&download=1"
        return PlaybackUrlResponse(
            url=f"/api/media/stream?{query}",
            expires_in=settings.playback_url_expire_seconds,
        )
    try:
        url = s3.presigned_get(key, filename=Path(filename).name, download=download)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Falha ao gerar URL de reprodução") from exc
    return PlaybackUrlResponse(url=url, expires_in=settings.playback_url_expire_seconds)


@router.get("/stream")
def media_stream(
    request: Request,
    id: str = Query(..., min_length=1),
    folder: FolderKind = Query("downloads"),
    download: bool = Query(False),
    usuario: Usuario = Depends(get_current_user),
):
    db = SessionLocal()
    storage_key = None
    filename = None
    try:
        storage_key, _, filename = library.storage_keys_for(db, id, folder, usuario.id)
    finally:
        db.close()

    if storage_key and filename:
        try:
            media_type = s3.content_type_for(filename)
            return _stream_s3(storage_key, Path(filename).name, media_type, download, request)
        except Exception as exc:
            raise HTTPException(status_code=404, detail="Arquivo não encontrado") from exc

    raise HTTPException(status_code=404, detail="Arquivo não encontrado")


@router.get("/thumb")
def media_thumb(
    request: Request,
    id: str = Query(..., min_length=1),
    folder: FolderKind = Query("downloads"),
    usuario: Usuario = Depends(get_current_user),
):
    db = SessionLocal()
    thumb_key = None
    filename = None
    try:
        _, thumb_key, filename = library.storage_keys_for(db, id, folder, usuario.id)
    finally:
        db.close()

    if thumb_key and filename:
        try:
            return _stream_s3(
                thumb_key,
                Path(filename).with_suffix(".jpg").name,
                "image/jpeg",
                False,
                request,
                cache_seconds=_THUMB_CACHE_SECONDS,
            )
        except Exception as exc:
            raise HTTPException(status_code=404, detail="Thumbnail não encontrada") from exc

    raise HTTPException(status_code=404, detail="Thumbnail não encontrada")


@router.delete("", response_model=DeleteMediaResponse)
def media_delete(
    id: str = Query(..., min_length=1),
    folder: FolderKind = Query("downloads"),
    usuario: Usuario = Depends(get_current_user),
) -> DeleteMediaResponse:
    deleted, cortes_deleted = library.delete_library_media(id, folder, usuario.id)
    return DeleteMediaResponse(deleted=deleted, cortes_deleted=cortes_deleted)
