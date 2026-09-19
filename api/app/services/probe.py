from __future__ import annotations

import json
import subprocess
from pathlib import Path

from app.models.schemas import MediaInfo


def probe_media(path: Path) -> MediaInfo:
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Falha ao ler metadados do vídeo")

    data = json.loads(result.stdout)
    duration = float(data.get("format", {}).get("duration") or 0)
    width = None
    height = None
    for stream in data.get("streams") or []:
        if stream.get("codec_type") == "video":
            width = stream.get("width")
            height = stream.get("height")
            break

    return MediaInfo(
        name=path.name,
        duration=duration,
        width=width,
        height=height,
        size=path.stat().st_size,
    )


def ensure_faststart(path: Path) -> Path:
    """Move o índice MP4 para o início (moov) para o player começar sem baixar o arquivo todo."""
    if path.suffix.lower() not in {".mp4", ".m4v", ".mov"}:
        return path
    dest = path.with_name(f"{path.stem}.faststart{path.suffix}")
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not dest.is_file() or dest.stat().st_size <= 0:
        dest.unlink(missing_ok=True)
        return path
    path.unlink(missing_ok=True)
    dest.rename(path)
    return path
