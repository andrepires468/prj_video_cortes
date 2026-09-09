from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

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

_STATUS_ID_RE = re.compile(r"/status(?:es)?/(\d+)", re.IGNORECASE)
_STATUS_URL_RE = re.compile(
    r"https?://(?:www\.|mobile\.|m\.)?(?:x|twitter)\.com/[^/\s]+/status/\d+",
    re.IGNORECASE,
)
_FX_API = "https://api.fxtwitter.com/status/{tweet_id}"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _tweet_id(url: str) -> str | None:
    match = _STATUS_ID_RE.search(url)
    return match.group(1) if match else None


def _http_json(url: str) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _fetch_fx_tweet(tweet_id: str) -> dict[str, Any]:
    data = _http_json(_FX_API.format(tweet_id=tweet_id))
    tweet = data.get("tweet")
    if not isinstance(tweet, dict):
        raise RuntimeError("Não foi possível ler os metadados do post no X.")
    return tweet


def _quoted_status_url(tweet: dict[str, Any]) -> str | None:
    raw = tweet.get("raw_text") if isinstance(tweet.get("raw_text"), dict) else {}
    for facet in raw.get("facets") or []:
        if not isinstance(facet, dict):
            continue
        for key in ("replacement", "original"):
            value = str(facet.get(key) or "")
            match = _STATUS_URL_RE.search(value)
            if match:
                return match.group(0)
    for key in ("quote", "quoted_tweet", "retweeted_tweet"):
        nested = tweet.get(key)
        if isinstance(nested, dict):
            url = nested.get("url") or ""
            if _tweet_id(str(url)):
                return str(url)
    return None


def _best_mp4_url(tweet: dict[str, Any]) -> str | None:
    media = tweet.get("media") if isinstance(tweet.get("media"), dict) else {}
    videos = media.get("videos") or media.get("all") or []
    best_url: str | None = None
    best_bitrate = -1
    for video in videos:
        if not isinstance(video, dict):
            continue
        if video.get("type") not in (None, "video", "gif"):
            continue
        candidates = list(video.get("formats") or []) + list(video.get("variants") or [])
        if video.get("url"):
            candidates.append(video)
        for fmt in candidates:
            if not isinstance(fmt, dict):
                continue
            url = str(fmt.get("url") or "")
            if ".mp4" not in url.split("?")[0].lower():
                continue
            bitrate = fmt.get("bitrate") or 0
            try:
                bitrate = int(bitrate)
            except (TypeError, ValueError):
                bitrate = 0
            if bitrate > best_bitrate:
                best_bitrate = bitrate
                best_url = url
    return best_url


class XProvider:
    """Download de vídeos do X (Twitter) via yt-dlp, com fallback para citação/embed."""

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
        try:
            return self._download_ytdlp(url, dest_dir, progress_cb)
        except Exception as exc:
            if not self._is_missing_video_error(exc):
                raise
            return self._download_embedded(url, dest_dir, progress_cb, exc)

    @staticmethod
    def _is_missing_video_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        return "no video could be found" in msg or ("no video" in msg and "tweet" in msg)

    def _download_embedded(
        self,
        url: str,
        dest_dir: Path,
        progress_cb: ProgressCallback | None,
        original_exc: Exception,
    ) -> Path:
        tweet_id = _tweet_id(url)
        if not tweet_id:
            raise original_exc

        if progress_cb:
            progress_cb(4.0, "Vídeo não veio no post; buscando citação/embed…")

        try:
            tweet = _fetch_fx_tweet(tweet_id)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as fx_exc:
            raise RuntimeError(
                "Este post do X não tem vídeo baixável diretamente "
                "(pode ser citação, foto ou conteúdo protegido)."
            ) from fx_exc

        quoted = _quoted_status_url(tweet)
        quoted_id = _tweet_id(quoted or "")
        if quoted and quoted_id and quoted_id != tweet_id:
            if progress_cb:
                progress_cb(8.0, "Baixando o vídeo original da citação…")
            try:
                return self._download_ytdlp(quoted, dest_dir, progress_cb)
            except Exception:
                pass

        mp4_url = _best_mp4_url(tweet)
        if not mp4_url:
            raise RuntimeError(
                "Este post do X não tem vídeo baixável (pode ser só texto, foto ou vídeo protegido)."
            ) from original_exc

        if progress_cb:
            progress_cb(10.0, "Baixando vídeo embutido do X…")

        tmp_path = dest_dir / f"{tweet_id}.mp4"
        self._download_direct(mp4_url, tmp_path, progress_cb)
        return self._finalize_file(tmp_path, dest_dir, tweet, tweet_id, progress_cb)

    def _download_ytdlp(
        self,
        url: str,
        dest_dir: Path,
        progress_cb: ProgressCallback | None = None,
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
            "format": "best[ext=mp4]/bestvideo*+bestaudio/best",
            "merge_output_format": "mp4",
            "noplaylist": True,
            "progress_hooks": [_hook],
            "quiet": True,
            "no_warnings": True,
            "restrictfilenames": False,
            "windowsfilenames": True,
            "http_headers": {"User-Agent": _UA},
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

        return self._rename_final(path, dest_dir, title or "x_video", str(video_id), progress_cb)

    def _download_direct(
        self,
        url: str,
        dest: Path,
        progress_cb: ProgressCallback | None,
    ) -> None:
        req = Request(url, headers={"User-Agent": _UA, "Referer": "https://x.com/"})
        with urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            downloaded = 0
            with dest.open("wb") as handle:
                while True:
                    chunk = resp.read(256 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total:
                        pct = downloaded / total * 99.0
                        progress_cb(min(pct, 99.0), f"Baixando do X… {pct:.1f}%")

    def _finalize_file(
        self,
        path: Path,
        dest_dir: Path,
        tweet: dict[str, Any],
        tweet_id: str,
        progress_cb: ProgressCallback | None,
    ) -> Path:
        author = tweet.get("author") if isinstance(tweet.get("author"), dict) else {}
        uploader = str(author.get("screen_name") or author.get("name") or "").strip()
        raw_title = str(tweet.get("text") or "").strip()
        if uploader and raw_title:
            title = f"{uploader}_{raw_title[:60]}"
        else:
            title = raw_title or uploader or "x_video"
        return self._rename_final(path, dest_dir, title, tweet_id, progress_cb)

    def _rename_final(
        self,
        path: Path,
        dest_dir: Path,
        title: str,
        video_id: str,
        progress_cb: ProgressCallback | None,
    ) -> Path:
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
