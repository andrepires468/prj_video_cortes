from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL

from app.config import settings
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

_FORMAT = "bv*+ba/b/bestvideo*+bestaudio/best"
_BOT_MARKERS = (
    "sign in to confirm you're not a bot",
    "confirm you're not a bot",
    "cookies-from-browser",
    "use --cookies",
)


def _is_bot_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in _BOT_MARKERS)


def _player_clients() -> list[str | None]:
    raw = (settings.youtube_player_clients or "").strip()
    clients = [item.strip() for item in raw.split(",") if item.strip()]
    if not clients:
        return [None]
    return clients


def _cookies_opts() -> dict[str, Any]:
    cookies_path = (settings.ytdlp_cookies_file or "").strip()
    if not cookies_path:
        return {}
    path = Path(cookies_path)
    if not path.is_file():
        return {}
    return {"cookiefile": str(path)}


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
        errors: list[str] = []

        for client in _player_clients():
            try:
                return self._download_with_client(url, dest_dir, progress_cb, client)
            except Exception as exc:
                errors.append(f"{client or 'default'}: {exc}")
                if not _is_bot_error(exc):
                    raise
                if progress_cb:
                    progress_cb(2.0, "YouTube bloqueou o servidor; tentando outro client…")

        hint = (
            "YouTube pediu confirmação anti-bot no servidor. "
            "Configure YTDLP_COOKIES_FILE no EasyPanel com cookies exportados do navegador "
            "(formato Netscape) e tente de novo."
        )
        detail = "; ".join(errors[-2:]) if errors else hint
        raise RuntimeError(f"{hint} Detalhe: {detail}") from None

    def _download_with_client(
        self,
        url: str,
        dest_dir: Path,
        progress_cb: ProgressCallback | None,
        player_client: str | None,
    ) -> Path:
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
            "format": _FORMAT,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "progress_hooks": [_hook],
            "quiet": True,
            "no_warnings": True,
            "restrictfilenames": False,
            "windowsfilenames": True,
            **_cookies_opts(),
        }
        if player_client:
            opts["extractor_args"] = {"youtube": {"player_client": [player_client]}}

        info: dict[str, Any] | None = None
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if result_path["path"] is None and info:
                    prepared = Path(ydl.prepare_filename(info))
                    if not prepared.exists():
                        mp4 = prepared.with_suffix(".mp4")
                        if mp4.exists():
                            prepared = mp4
                    result_path["path"] = prepared
        except Exception:
            self._cleanup_partial(dest_dir)
            raise

        path = result_path["path"]
        if path is None or not path.exists():
            self._cleanup_partial(dest_dir)
            raise RuntimeError("Download concluído, mas o arquivo não foi encontrado.")

        height = int((info or {}).get("height") or 0)
        if player_client == "android" and height and height <= 360 and progress_cb:
            progress_cb(
                99.0,
                "Download em 360p (fallback Android). Para 1080p, configure YTDLP_COOKIES_FILE.",
            )

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
        elif path.suffix != path.suffix.lower():
            lowered = path.with_suffix(path.suffix.lower())
            if lowered != path:
                if lowered.exists():
                    lowered.unlink()
                path = path.rename(lowered)

        if progress_cb:
            progress_cb(100.0, "Download concluído")
        return path

    @staticmethod
    def _cleanup_partial(dest_dir: Path) -> None:
        for pattern in ("*.mp4", "*.webm", "*.mkv", "*.m4a", "*.part", "*.ytdl"):
            for item in dest_dir.glob(pattern):
                try:
                    item.unlink(missing_ok=True)
                except OSError:
                    pass
        for item in dest_dir.glob("*.temp"):
            shutil.rmtree(item, ignore_errors=True)
