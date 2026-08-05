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
