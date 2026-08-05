from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL

from app.providers.base import ProgressCallback
from app.services.filenames import build_video_filename

_YOUTUBE_HOSTS = (
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
    "music.youtube.com",
)


class YoutubeProvider:
    """Download provider backed by yt-dlp for YouTube URLs."""

    def can_handle(self, url: str) -> bool:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url.strip())
            host = (parsed.hostname or "").lower()
            if host in _YOUTUBE_HOSTS:
                return True
            return bool(
                re.match(
                    r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/",
                    url.strip(),
                    re.IGNORECASE,
                )
            )
        except Exception:
            return False

    def download(
        self,
        url: str,
        dest_dir: Path,
        progress_cb: ProgressCallback | None = None,
    ) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        # Nome temporário pelo id; renomeamos ao final com o padrão sanitizado
        outtmpl = str(dest_dir / "%(id)s.%(ext)s")
        result_path: dict[str, Path | None] = {"path": None}

        def _hook(d: dict[str, Any]) -> None:
            status = d.get("status")
            if status == "downloading" and progress_cb:
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                pct = (downloaded / total * 100.0) if total else 0.0
                speed = d.get("_speed_str") or ""
                eta = d.get("_eta_str") or ""
                msg = f"Baixando… {pct:.1f}%"
                if speed:
                    msg += f" ({speed})"
                if eta:
                    msg += f" ETA {eta}"
                progress_cb(min(pct, 99.0), msg)
            elif status == "finished":
                filename = d.get("filename")
                if filename:
                    result_path["path"] = Path(filename)
                if progress_cb:
                    progress_cb(99.0, "Processando / mesclando…")

        opts: dict[str, Any] = {
            "outtmpl": outtmpl,
            "format": (
                "bv*[ext=mp4]+ba[ext=m4a]/"
                "bv*+ba/b/"
                "bestvideo*+bestaudio/best"
            ),
            "merge_output_format": "mp4",
            "noplaylist": True,
            "progress_hooks": [_hook],
            "quiet": True,
            "no_warnings": True,
            "restrictfilenames": False,
            "windowsfilenames": True,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web", "ios"],
                }
            },
        }

        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if result_path["path"] is None and info:
                prepared = Path(ydl.prepare_filename(info))
                if not prepared.exists():
                    mp4 = prepared.with_suffix(".mp4")
                    if mp4.exists():
                        prepared = mp4
                result_path["path"] = prepared

        path = result_path["path"]
        if path is None or not path.exists():
            raise RuntimeError("Download concluído, mas o arquivo não foi encontrado.")

        title = (info or {}).get("title") if info else None
        video_id = (info or {}).get("id") if info else None
        if not video_id:
            video_id = path.stem

        final_name = build_video_filename(
            title=title or "video",
            video_id=str(video_id),
            ext=path.suffix or "mp4",
        )
        final_path = dest_dir / final_name

        if path.resolve() != final_path.resolve():
            if final_path.exists():
                final_path.unlink()
            path = path.rename(final_path)
        else:
            # Garante extensão em minúsculo mesmo se o nome já bater
            if path.suffix != path.suffix.lower():
                lowered = path.with_suffix(path.suffix.lower())
                if lowered != path:
                    if lowered.exists():
                        lowered.unlink()
                    path = path.rename(lowered)

        if progress_cb:
            progress_cb(100.0, "Download concluído")
        return path
