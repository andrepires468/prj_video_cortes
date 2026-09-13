from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.db import check_database
from app.models.schemas import HealthResponse
from app.routers import auth, downloads, editor, media
from app.services.storage import ensure_cortes_dir, ensure_downloads_dir

app = FastAPI(title="Video Cortes API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3101",
        "http://127.0.0.1:3101",
    ],
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
    ensure_downloads_dir()
    ensure_cortes_dir()
    check_database()


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        check_database()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return HealthResponse(status="ok", database="ok")
