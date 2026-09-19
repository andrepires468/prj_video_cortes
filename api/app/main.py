from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import check_database
from app.models.schemas import HealthResponse
from app.routers import auth, downloads, editor, media
from app.services import s3

app = FastAPI(title="Video Cortes API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(downloads.router)
app.include_router(media.router)
app.include_router(editor.router)


@app.on_event("startup")
def on_startup() -> None:
    # Não derruba o processo: /api/health precisa responder mesmo com DB/MinIO fora.
    try:
        s3.ensure_playback_cors()
    except Exception:
        pass


def _safe_error(exc: BaseException) -> str:
    msg = f"{type(exc).__name__}: {exc}"
    for secret in (settings.mysql_pass, settings.minio_secret_key, settings.jwt_secret):
        if secret:
            msg = msg.replace(secret, "***")
    return msg[:800]


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    errors: dict[str, str] = {}

    try:
        check_database()
        database = "ok"
    except Exception as exc:
        database = "error"
        errors["database"] = _safe_error(exc)

    try:
        s3.check_storage()
        storage = "ok"
    except Exception as exc:
        storage = "error"
        errors["storage"] = _safe_error(exc)

    return HealthResponse(
        status="ok" if not errors else "error",
        database=database,
        storage=storage,
        errors=errors,
    )
