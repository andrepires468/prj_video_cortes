from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models.schemas import HealthResponse
from app.routers import downloads, editor, media
from app.services.storage import ensure_cortes_dir, ensure_downloads_dir

app = FastAPI(title="Video Cortes API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(downloads.router)
app.include_router(media.router)
app.include_router(editor.router)


@app.on_event("startup")
def on_startup() -> None:
    ensure_downloads_dir()
    ensure_cortes_dir()


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
