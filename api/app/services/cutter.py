from __future__ import annotations

import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.models.schemas import CutJobInfo, CutSegment, JobStatus
from app.services.filenames import safe_video_stem
from app.services.probe import probe_media
from app.services.storage import (
    corte_belongs_to,
    ensure_cortes_dir,
    resolve_download_file,
    resolve_media_file,
)
from app.services.thumbnail import generate_thumbnail

_lock = threading.Lock()
_jobs: dict[str, CutJobInfo] = {}

SPEED_MIN = 0.25
SPEED_MAX = 2.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _update_job(job_id: str, **kwargs) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        data = job.model_dump()
        data.update(kwargs)
        data["updated_at"] = _now()
        _jobs[job_id] = CutJobInfo(**data)


def get_job(job_id: str) -> CutJobInfo | None:
    with _lock:
        return _jobs.get(job_id)


def markers_to_segments(markers: list[float], duration: float) -> list[CutSegment]:
    """0 linhas = vídeo inteiro; 2 linhas = trecho entre elas; 1 linha é inválido."""
    points = sorted(m for m in markers if 0 < m < duration)
    unique: list[float] = []
    for m in points:
        if not unique or abs(unique[-1] - m) >= 0.05:
            unique.append(m)

    if len(unique) == 0:
        if duration < 0.05:
            raise ValueError("A duração do vídeo é muito curta para exportar.")
        return [CutSegment(start=0.0, end=duration)]

    if len(unique) == 1:
        raise ValueError(
            "Não é possível salvar com apenas 1 linha de corte. "
            "Posicione a segunda linha ou remova a linha para salvar o vídeo inteiro."
        )

    if len(unique) != 2:
        raise ValueError("Posicione no máximo 2 linhas de corte para salvar.")

    start, end = unique[0], unique[1]
    if end - start < 0.05:
        raise ValueError("O intervalo entre as linhas de corte é muito curto.")

    return [CutSegment(start=start, end=end)]


def _clamp_speed(speed: float) -> float:
    try:
        value = float(speed)
    except (TypeError, ValueError):
        return 1.0
    return min(SPEED_MAX, max(SPEED_MIN, round(value, 2)))


def _atempo_filter(speed: float) -> str:
    """atempo aceita 0.5–2.0; encadeia filtros para cobrir 0.25–2.0."""
    remaining = speed
    parts: list[str] = []
    while remaining < 0.5 - 1e-9:
        parts.append("atempo=0.5")
        remaining /= 0.5
    while remaining > 2.0 + 1e-9:
        parts.append("atempo=2.0")
        remaining /= 2.0
    if abs(remaining - 1.0) > 1e-3:
        parts.append(f"atempo={remaining:.4f}")
    return ",".join(parts)


def create_cut_job(
    filename: str,
    markers: list[float],
    segments: list[CutSegment] | None = None,
    speed: float = 1.0,
    source_filename: str | None = None,
) -> CutJobInfo:
    original = resolve_download_file(filename)
    if source_filename:
        if not corte_belongs_to(filename, source_filename):
            raise ValueError("O arquivo informado não é um corte deste vídeo.")
        path = resolve_media_file(source_filename, "cortes")
    else:
        path = original
    info = probe_media(path)
    if info.duration <= 0:
        raise ValueError("Duração do vídeo inválida")

    if segments:
        resolved = [
            CutSegment(start=max(0.0, s.start), end=min(info.duration, s.end))
            for s in segments
            if s.end > s.start
        ]
    else:
        resolved = markers_to_segments(markers, info.duration)

    if not resolved:
        raise ValueError("Nenhum segmento válido para exportar.")

    job_id = str(uuid.uuid4())
    job = CutJobInfo(
        id=job_id,
        status=JobStatus.queued,
        progress=0.0,
        message="Na fila",
        filename=filename,
        outputs=[],
        created_at=_now(),
        updated_at=_now(),
    )
    with _lock:
        _jobs[job_id] = job

    thread = threading.Thread(
        target=_run_cuts,
        args=(job_id, path, resolved, _clamp_speed(speed), filename),
        daemon=True,
    )
    thread.start()
    return job


def _safe_stem(name: str) -> str:
    return safe_video_stem(name)


def _run_cuts(
    job_id: str,
    source: Path,
    segments: list[CutSegment],
    speed: float = 1.0,
    output_filename: str | None = None,
) -> None:
    _update_job(job_id, status=JobStatus.running, message="Exportando cortes…", progress=0.0)
    outputs: list[str] = []
    dest_dir = ensure_cortes_dir()
    stem = _safe_stem(output_filename or source.name)
    # Reencode sempre em MP4 (H.264/AAC) para corte preciso no frame
    ext = ".mp4"

    try:
        total = len(segments)
        for index, segment in enumerate(segments, start=1):
            out_name = f"{stem}_corte_{index:02d}{ext}"
            out_path = dest_dir / out_name
            # Evita sobrescrever: se existir, incrementa sufixo
            counter = 1
            while out_path.exists():
                counter += 1
                out_name = f"{stem}_corte_{index:02d}_{counter}{ext}"
                out_path = dest_dir / out_name

            _update_job(
                job_id,
                message=f"Exportando corte {index}/{total}…",
                progress=round((index - 1) / total * 100, 1),
            )
            _ffmpeg_cut(source, out_path, segment.start, segment.end, speed)
            try:
                generate_thumbnail(out_path)
            except Exception:  # noqa: BLE001 — corte ok mesmo se thumb falhar
                pass
            outputs.append(out_name)

        _update_job(
            job_id,
            status=JobStatus.done,
            progress=100.0,
            message=f"{len(outputs)} arquivo(s) gerado(s)",
            outputs=outputs,
            error=None,
        )
    except Exception as exc:  # noqa: BLE001
        _update_job(
            job_id,
            status=JobStatus.error,
            message="Falha ao exportar cortes",
            error=str(exc),
            outputs=outputs,
        )


_ENCODE_ARGS = [
    "-c:v",
    "libx264",
    "-preset",
    "veryfast",
    "-crf",
    "18",
    "-pix_fmt",
    "yuv420p",
    "-c:a",
    "aac",
    "-b:a",
    "192k",
    "-movflags",
    "+faststart",
]


def _speed_filter_args(speed: float) -> list[str]:
    if abs(speed - 1.0) < 0.01:
        return []
    args = ["-filter:v", f"setpts=PTS/{speed:.4f}"]
    atempo = _atempo_filter(speed)
    if atempo:
        args += ["-filter:a", atempo]
    return args


def _ffmpeg_cut(source: Path, dest: Path, start: float, end: float, speed: float = 1.0) -> None:
    """
    Corte com reencode (não usa -c copy).

    A velocidade altera só o arquivo gerado em data/cortes; o original
    em downloads permanece intacto.
    """
    duration = max(0.05, end - start)
    speed = _clamp_speed(speed)
    speed_args = _speed_filter_args(speed)

    # -ss/-t antes de -i: recorta a duração original no input; os filtros
    # de velocidade mudam só a duração do arquivo de saída.
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(source),
        *speed_args,
        *_ENCODE_ARGS,
        str(dest),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode == 0:
        return

    # Fallback: trim no filtro (preciso mesmo com velocidade != 1.0)
    v_filters = [f"trim=start={start:.3f}:duration={duration:.3f}", "setpts=PTS-STARTPTS"]
    a_filters = [f"atrim=start={start:.3f}:duration={duration:.3f}", "asetpts=PTS-STARTPTS"]
    if abs(speed - 1.0) >= 0.01:
        v_filters.append(f"setpts=PTS/{speed:.4f}")
        atempo = _atempo_filter(speed)
        if atempo:
            a_filters.append(atempo)

    cmd_slow = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-filter:v",
        ",".join(v_filters),
        "-filter:a",
        ",".join(a_filters),
        *_ENCODE_ARGS,
        str(dest),
    ]
    result2 = subprocess.run(cmd_slow, capture_output=True, text=True, check=False)
    if result2.returncode != 0:
        raise RuntimeError(
            result2.stderr.strip() or result.stderr.strip() or "FFmpeg falhou"
        )
