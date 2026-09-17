from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from minio import Minio
from minio.error import S3Error

from app.config import settings

_cors_ok = False

_CONTENT_TYPES = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".m4v": "video/x-m4v",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _endpoint() -> str:
    value = (settings.minio_endpoint or "").strip()
    value = value.replace("https://", "").replace("http://", "")
    return value.rstrip("/")


@lru_cache(maxsize=1)
def get_client() -> Minio:
    return Minio(
        _endpoint(),
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_use_ssl,
        region=settings.minio_region or None,
    )


def content_type_for(filename: str) -> str:
    return _CONTENT_TYPES.get(Path(filename).suffix.lower(), "application/octet-stream")


def download_object_key(usuario_id: str, download_id: str, filename: str) -> str:
    return f"downloads/{usuario_id}/{download_id}/{filename}"


def download_thumb_key(usuario_id: str, download_id: str, stem: str) -> str:
    return f"downloads/{usuario_id}/{download_id}/{stem}.jpg"


def corte_object_key(usuario_id: str, download_id: str, corte_id: str, filename: str) -> str:
    return f"cortes/{usuario_id}/{download_id}/{corte_id}/{filename}"


def corte_thumb_key(usuario_id: str, download_id: str, corte_id: str, stem: str) -> str:
    return f"cortes/{usuario_id}/{download_id}/{corte_id}/{stem}.jpg"


class _ProgressReader:
    def __init__(
        self,
        handle,
        size: int,
        on_progress: Callable[[float], None] | None = None,
        check: Callable[[], None] | None = None,
    ) -> None:
        self._handle = handle
        self._size = size
        self._on_progress = on_progress
        self._check = check
        self._seen = 0

    def read(self, amt: int = -1) -> bytes:
        if self._check:
            self._check()
        data = self._handle.read(amt)
        if data:
            self._seen += len(data)
            if self._on_progress and self._size:
                self._on_progress(min(self._seen / self._size * 100.0, 100.0))
        return data

    def seek(self, offset: int, whence: int = 0) -> int:
        result = self._handle.seek(offset, whence)
        self._seen = self._handle.tell()
        return result

    def tell(self) -> int:
        return self._handle.tell()

    def readable(self) -> bool:
        return True


def put_file(
    key: str,
    path: Path,
    content_type: str | None = None,
    on_progress: Callable[[float], None] | None = None,
    check: Callable[[], None] | None = None,
) -> str:
    client = get_client()
    ctype = content_type or content_type_for(path.name)
    if on_progress is None and check is None:
        client.fput_object(
            settings.minio_bucket,
            key,
            str(path),
            content_type=ctype,
        )
        return key
    size = int(path.stat().st_size)
    with path.open("rb") as handle:
        reader = _ProgressReader(handle, size, on_progress, check)
        client.put_object(
            settings.minio_bucket,
            key,
            reader,
            size,
            content_type=ctype,
        )
    return key


def get_file(key: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    get_client().fget_object(settings.minio_bucket, key, str(dest))
    return dest


def object_exists(key: str) -> bool:
    if not key:
        return False
    try:
        get_client().stat_object(settings.minio_bucket, key)
        return True
    except S3Error:
        return False


def stat_object(key: str):
    return get_client().stat_object(settings.minio_bucket, key)


def get_object(key: str, offset: int = 0, length: int | None = None):
    kwargs: dict = {}
    if offset:
        kwargs["offset"] = offset
    if length is not None:
        kwargs["length"] = length
    return get_client().get_object(settings.minio_bucket, key, **kwargs)


def remove_object(key: str | None) -> None:
    if not key:
        return
    try:
        get_client().remove_object(settings.minio_bucket, key)
    except S3Error:
        return


def presigned_get(
    key: str,
    expires_seconds: int | None = None,
    filename: str | None = None,
    download: bool = False,
) -> str:
    extra: dict[str, str] = {}
    if filename:
        extra["response-content-type"] = content_type_for(filename)
        disposition = "attachment" if download else "inline"
        extra["response-content-disposition"] = f'{disposition}; filename="{Path(filename).name}"'
    return get_client().presigned_get_object(
        settings.minio_bucket,
        key,
        expires=timedelta(seconds=expires_seconds or settings.playback_url_expire_seconds),
        response_headers=extra or None,
    )


def playback_cors_ok() -> bool:
    return _cors_ok


def ensure_playback_cors() -> None:
    """Lê o CORS do bucket. Não grava: o gateway EasyPanel não implementa PUT ?cors."""
    global _cors_ok
    _cors_ok = False
    origins = [item.strip() for item in (settings.minio_cors_origins or "").split(",") if item.strip()]
    if not origins:
        return
    try:
        response = get_client()._execute(
            "GET",
            settings.minio_bucket,
            query_params={"cors": ""},
        )
        body = (response.data or b"").decode("utf-8", errors="ignore")
        response.close()
        response.release_conn()
    except S3Error:
        return
    except Exception:
        return
    _cors_ok = any(origin in body for origin in origins)
