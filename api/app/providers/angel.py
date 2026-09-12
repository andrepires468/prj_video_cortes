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

_ANGEL_HOSTS = (
    "angel.com",
    "www.angel.com",
    "m.angel.com",
    "watch.angel.com",
    "angelstudios.com",
    "www.angelstudios.com",
    "watch.angelstudios.com",
)

_GUID_RE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)
_EPISODE_PATH_RE = re.compile(
    r"/episode/"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)
_GRAPHQL_URL = "https://api.angelstudios.com/graphql"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.angel.com/",
    "Origin": "https://www.angel.com",
}

_EPISODE_QUERY = """
query getEpisodeByGuid($guid: ID!, $streamingArgs: StreamingUrlArgs) {
  episode(guid: $guid) {
    id
    guid
    slug
    episodeNumber
    seasonNumber
    name
    subtitle
    description
    projectSlug
    isAngelGuildOnly
    unavailableReason
    source {
      credits
      duration
      url(input: $streamingArgs)
    }
  }
}
"""


def _normalize_url(url: str) -> str:
    raw = url.strip()
    if "://" not in raw:
        return f"https://{raw}"
    return raw


def _guid_from_url(url: str) -> str | None:
    match = _GUID_RE.search(url)
    return match.group(1).lower() if match else None


def _http_get(url: str) -> str:
    req = Request(url, headers=_HEADERS)
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _http_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    headers = {
        **_HEADERS,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _slug_to_title(slug: str) -> str:
    return re.sub(r"[-_]+", " ", slug or "").strip().title()


def _looks_like_m3u8(value: Any) -> bool:
    return isinstance(value, str) and ".m3u8" in value.split("?")[0].lower()


def _season_episode_tag(season: Any, episode: Any) -> str:
    try:
        season_n = int(season)
        episode_n = int(episode)
    except (TypeError, ValueError):
        return ""
    if season_n <= 0 or episode_n <= 0:
        return ""
    return f"S{season_n:02d}E{episode_n:02d}"


def _build_title(meta: dict[str, Any]) -> str:
    project = (
        meta.get("project_name")
        or _slug_to_title(str(meta.get("project_slug") or ""))
        or "Angel"
    )
    subtitle = str(meta.get("subtitle") or "").strip()
    name = str(meta.get("name") or "").strip()
    tag = _season_episode_tag(meta.get("season_number"), meta.get("episode_number"))

    # "Episode 1" sozinho não ajuda; o subtítulo costuma ser o título real.
    episode_label = bool(re.match(r"^episode\s+\d+$", name, re.IGNORECASE))
    pretty_name = "" if episode_label else name

    parts = [project]
    if tag:
        parts.append(tag)
    if subtitle and subtitle.lower() not in project.lower():
        parts.append(subtitle)
    elif pretty_name and pretty_name.lower() not in project.lower():
        parts.append(pretty_name)
    return " ".join(p for p in parts if p) or "angel"


def _walk_source(obj: Any, prefer_guid: str | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """Procura um bloco com source.url HLS, preferindo o GUID do episódio."""
    found_meta: dict[str, Any] | None = None
    found_url: str | None = None

    def visit(node: Any) -> None:
        nonlocal found_meta, found_url
        if isinstance(node, dict):
            source = node.get("source")
            url = None
            if isinstance(source, dict) and _looks_like_m3u8(source.get("url")):
                url = str(source["url"])
            elif _looks_like_m3u8(node.get("url")) and node.get("__typename") in (
                "EpisodeSource",
                "Episode",
                None,
            ):
                url = str(node["url"])
            if url:
                node_id = str(node.get("guid") or node.get("id") or "").lower()
                if prefer_guid and node_id == prefer_guid:
                    found_meta = node
                    found_url = url
                    return
                if found_url is None:
                    found_meta = node
                    found_url = url
            for value in node.values():
                if found_meta is not None and prefer_guid and str(
                    (found_meta.get("guid") or found_meta.get("id") or "")
                ).lower() == prefer_guid:
                    return
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(obj)
    return found_meta, found_url


def _meta_from_episode(episode: dict[str, Any], project_name: str | None = None) -> dict[str, Any]:
    source = episode.get("source") if isinstance(episode.get("source"), dict) else {}
    return {
        "id": str(episode.get("guid") or episode.get("id") or "").lower(),
        "name": episode.get("name") or "",
        "subtitle": episode.get("subtitle") or "",
        "project_slug": episode.get("projectSlug") or "",
        "project_name": project_name or "",
        "season_number": episode.get("seasonNumber"),
        "episode_number": episode.get("episodeNumber"),
        "stream_url": source.get("url") if _looks_like_m3u8(source.get("url")) else None,
        "is_guild_only": bool(episode.get("isAngelGuildOnly")),
        "unavailable": episode.get("unavailableReason"),
    }


def _fetch_graphql_episode(guid: str) -> dict[str, Any] | None:
    data = _http_json(
        _GRAPHQL_URL,
        {
            "query": _EPISODE_QUERY,
            "operationName": "getEpisodeByGuid",
            "variables": {"guid": guid, "streamingArgs": None},
        },
    )
    episode = (data.get("data") or {}).get("episode")
    if not isinstance(episode, dict):
        return None
    return _meta_from_episode(episode)


def _parse_next_data(html: str) -> dict[str, Any] | None:
    match = _NEXT_DATA_RE.search(html)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _fetch_from_webpage(url: str, guid: str | None) -> dict[str, Any]:
    html = _http_get(url)
    next_data = _parse_next_data(html)
    page_props = ((next_data or {}).get("props") or {}).get("pageProps") or {}
    project = page_props.get("project") if isinstance(page_props.get("project"), dict) else {}
    project_name = str(project.get("name") or project.get("title") or "").strip()

    episode = page_props.get("episode")
    if isinstance(episode, dict):
        meta = _meta_from_episode(episode, project_name)
        if meta.get("stream_url"):
            return meta

    node, stream_url = _walk_source(page_props, guid)
    if stream_url:
        meta = _meta_from_episode(node or {}, project_name)
        meta["stream_url"] = stream_url
        if guid and not meta.get("id"):
            meta["id"] = guid
        return meta

    if guid is None:
        episode_ids = list(dict.fromkeys(item.lower() for item in _EPISODE_PATH_RE.findall(html)))
        # Página de filme costuma ter um episódio principal; série tem vários.
        if len(episode_ids) == 1:
            return {"id": episode_ids[0], "stream_url": None, "project_name": project_name}

    return {
        "id": guid or "",
        "stream_url": None,
        "project_name": project_name,
        "is_guild_only": False,
        "unavailable": None,
    }


class AngelProvider:
    """Download de episódios e filmes públicos da Angel (angel.com)."""

    def can_handle(self, url: str) -> bool:
        try:
            raw = _normalize_url(url)
            host = (urlparse(raw).hostname or "").lower()
            if host in _ANGEL_HOSTS or host.endswith(".angel.com") or host.endswith(".angelstudios.com"):
                return True
            return bool(
                re.match(
                    r"^(https?://)?((www|m|watch)\.)?(angel\.com|angelstudios\.com)/",
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
        page_url = _normalize_url(url)
        guid = _guid_from_url(page_url)
        meta: dict[str, Any] = {}

        if progress_cb:
            progress_cb(3.0, "Consultando metadados da Angel…")

        if guid:
            try:
                gql_meta = _fetch_graphql_episode(guid)
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError):
                gql_meta = None
            if gql_meta:
                meta = gql_meta

        if not meta.get("stream_url"):
            if progress_cb:
                progress_cb(6.0, "Lendo a página do episódio…")
            try:
                page_meta = _fetch_from_webpage(page_url, guid or meta.get("id"))
            except (HTTPError, URLError, TimeoutError) as exc:
                raise RuntimeError(
                    "Não foi possível acessar a página da Angel. Verifique a URL e a conexão."
                ) from exc
            for key, value in page_meta.items():
                if value not in (None, "", []) or key not in meta:
                    meta[key] = value
            if not guid and page_meta.get("id") and not page_meta.get("stream_url"):
                guid = str(page_meta["id"])
                try:
                    gql_meta = _fetch_graphql_episode(guid)
                except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError):
                    gql_meta = None
                if gql_meta and gql_meta.get("stream_url"):
                    meta = {**meta, **gql_meta}

        stream_url = meta.get("stream_url")
        video_id = str(meta.get("id") or guid or "").lower()
        if not stream_url:
            if meta.get("is_guild_only") or meta.get("unavailable"):
                reason = meta.get("unavailable") or "conteúdo exclusivo da Angel Guild"
                raise RuntimeError(
                    f"Este vídeo da Angel não está disponível sem login/assinatura ({reason})."
                )
            if not video_id:
                raise RuntimeError(
                    "Cole a URL do episódio ou filme da Angel (com o id no caminho), "
                    "não a página da série."
                )
            raise RuntimeError(
                "Não foi possível obter o stream deste vídeo da Angel. "
                "Pode exigir login, ser exclusivo da Guild ou estar bloqueado na sua região."
            )

        if progress_cb:
            progress_cb(10.0, "Baixando da Angel…")

        title = _build_title(meta)
        path = self._download_hls(stream_url, dest_dir, video_id or "angel", progress_cb)
        return self._rename_final(path, dest_dir, title, video_id or path.stem, progress_cb)

    def _download_hls(
        self,
        stream_url: str,
        dest_dir: Path,
        video_id: str,
        progress_cb: ProgressCallback | None,
    ) -> Path:
        outtmpl = str(dest_dir / f"{video_id}.%(ext)s")
        finished: list[Path] = []

        def _hook(d: dict[str, Any]) -> None:
            status = d.get("status")
            if status == "downloading" and progress_cb:
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                pct = (downloaded / total * 100.0) if total else 0.0
                # Reserva 10–99% para o HLS (metadados já usaram 0–10)
                scaled = 10.0 + min(pct, 99.0) * 0.88
                speed = d.get("_speed_str") or ""
                eta = d.get("_eta_str") or ""
                msg = f"Baixando da Angel… {pct:.1f}%"
                if speed:
                    msg += f" ({speed})"
                if eta:
                    msg += f" ETA {eta}"
                progress_cb(min(scaled, 98.0), msg)
            elif status == "finished":
                filename = d.get("filename")
                if filename:
                    finished.append(Path(filename))
                if progress_cb:
                    progress_cb(99.0, "Finalizando arquivo da Angel…")

        opts: dict[str, Any] = {
            "outtmpl": outtmpl,
            "format": (
                "bv*+ba[language=pt-BR]/"
                "bv*+ba[language^=pt]/"
                "bv*+ba[language^=en]/"
                "bv*+ba/b"
            ),
            "merge_output_format": "mp4",
            "noplaylist": True,
            "progress_hooks": [_hook],
            "quiet": True,
            "no_warnings": True,
            "restrictfilenames": False,
            "windowsfilenames": True,
            "hls_split_discontinuity": True,
            "overwrites": True,
            "concurrent_fragment_downloads": 4,
            "retries": 8,
            "fragment_retries": 8,
            "http_headers": {
                "User-Agent": _UA,
                "Referer": "https://www.angel.com/",
                "Origin": "https://www.angel.com",
            },
        }

        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(stream_url, download=True)
            if not finished and info:
                prepared = Path(ydl.prepare_filename(info))
                if prepared.exists():
                    finished.append(prepared)
                else:
                    for ext in (".mp4", ".mkv", ".ts"):
                        candidate = prepared.with_suffix(ext)
                        if candidate.exists():
                            finished.append(candidate)
                            break

        extras = [
            *dest_dir.glob(f"{video_id}.mp4"),
            *dest_dir.glob(f"{video_id}.*.mp4"),
            *dest_dir.glob(f"{video_id}.mkv"),
            *dest_dir.glob(f"{video_id}.*.mkv"),
        ]
        for extra in extras:
            if extra not in finished and extra.exists():
                finished.append(extra)

        existing = [path for path in finished if path.exists()]
        if not existing:
            raise RuntimeError(
                "Download da Angel concluído, mas o arquivo de vídeo não foi encontrado."
            )

        # Com hls_split_discontinuity o pré-roll vira arquivo pequeno; o episódio é o maior.
        path = max(existing, key=lambda item: item.stat().st_size)
        for leftover in existing:
            if leftover.resolve() != path.resolve():
                leftover.unlink(missing_ok=True)
        return path

    def _rename_final(
        self,
        path: Path,
        dest_dir: Path,
        title: str,
        video_id: str,
        progress_cb: ProgressCallback | None,
    ) -> Path:
        final_name = build_video_filename(
            title=title or "angel",
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
            progress_cb(100.0, "Download da Angel concluído")
        return path
