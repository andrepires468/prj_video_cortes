from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from yt_dlp import YoutubeDL

from app.providers.base import ProgressCallback
from app.services.filenames import build_video_filename

_X_HOSTS = (
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "mobile.twitter.com",
    "m.twitter.com",
    "vxtwitter.com",
    "fxtwitter.com",
)


class XProvider:
    """Download de vídeos do X (Twitter) via yt-dlp."""

    def can_handle(self, url: str) -> bool:
        try:
            raw = url.strip()
            parsed = urlparse(raw if "://" in raw else f"https://{raw}")
            host = (parsed.hostname or "").lower()
            if host in _X_HOSTS:
                return True
            return bool(
                re.match(
                    r"^(https?://)?(www\.|mobile\.|m\.)?(x|twitter)\.com/",
                    raw,
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
                msg = f"Baixando do X… {pct:.1f}%"
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
                    progress_cb(99.0, "Finalizando arquivo do X…")

        opts: dict[str, Any] = {
            "outtmpl": outtmpl,
            # X costuma servir MP4 progressivo; fallbacks cobrem variações
            "format": "best[ext=mp4]/bestvideo*+bestaudio/best",
            "merge_output_format": "mp4",
            "noplaylist": True,
            "progress_hooks": [_hook],
            "quiet": True,
            "no_warnings": True,
            "restrictfilenames": False,
            "windowsfilenames": True,
        }

        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if result_path["path"] is None and info:
                prepared = Path(ydl.prepare_filename(info))
                if not prepared.exists():
                    for ext in (".mp4", ".webm", ".mkv"):
                        candidate = prepared.with_suffix(ext)
                        if candidate.exists():
                            prepared = candidate
                            break
                result_path["path"] = prepared

        path = result_path["path"]
        if path is None or not path.exists():
            raise RuntimeError(
                "Download do X concluído, mas o arquivo de vídeo não foi encontrado. "
                "Verifique se o post contém vídeo."
            )

        title = None
        video_id = None
        if info:
            uploader = (info.get("uploader") or info.get("creator") or "").strip()
            raw_title = (info.get("title") or info.get("description") or "").strip()
            if uploader and raw_title:
                if raw_title.lower().startswith(uploader.lower()):
                    title = raw_title[:80]
                else:
                    title = f"{uploader}_{raw_title[:60]}"
            else:
                title = raw_title or uploader or "x_video"
            video_id = info.get("id")

        if not video_id:
            video_id = path.stem

        final_name = build_video_filename(
            title=title or "x_video",
            video_id=str(video_id),
            ext=path.suffix or "mp4",
        )
        final_path = dest_dir / final_name

        if path.resolve() != final_path.resolve():
            if final_path.exists():
                final_path.unlink()
            path = path.rename(final_path)
        elif path.suffix != path.suffix.lower():
            lowered = path.with_suffix(path.suffix.lower())
            if lowered != path:
                if lowered.exists():
                    lowered.unlink()
                path = path.rename(lowered)

        if progress_cb:
            progress_cb(100.0, "Download do X concluído")
        return path
