from __future__ import annotations

import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.models.schemas import CutJobInfo, CutSegment, JobStatus
from app.services.filenames import remove_special_chars
from app.services.probe import probe_media
from app.services.storage import ensure_cortes_dir, resolve_download_file

_lock = threading.Lock()
_jobs: dict[str, CutJobInfo] = {}


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
    """Exporta somente o trecho entre exatamente 2 linhas de corte."""
    points = sorted(m for m in markers if 0 < m < duration)
    # Deduplica pontos muito próximos
    unique: list[float] = []
    for m in points:
        if not unique or abs(unique[-1] - m) >= 0.05:
            unique.append(m)

    if len(unique) != 2:
        raise ValueError("É necessário posicionar exatamente 2 linhas de corte para salvar.")

    start, end = unique[0], unique[1]
    if end - start < 0.05:
        raise ValueError("O intervalo entre as linhas de corte é muito curto.")

    return [CutSegment(start=start, end=end)]


def create_cut_job(
    filename: str,
    markers: list[float],
    segments: list[CutSegment] | None = None,
) -> CutJobInfo:
    path = resolve_download_file(filename)
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
        args=(job_id, path, resolved),
        daemon=True,
    )
    thread.start()
    return job


def _safe_stem(name: str) -> str:
    stem = remove_special_chars(Path(name).stem)
    return (stem[:80] if stem else "clip")


def _run_cuts(job_id: str, source: Path, segments: list[CutSegment]) -> None:
    _update_job(job_id, status=JobStatus.running, message="Exportando cortes…", progress=0.0)
    outputs: list[str] = []
    dest_dir = ensure_cortes_dir()
    stem = _safe_stem(source.name)
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
            _ffmpeg_cut(source, out_path, segment.start, segment.end)
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


def _ffmpeg_cut(source: Path, dest: Path, start: float, end: float) -> None:
    """
    Corte com reencode (não usa -c copy).

    Com stream copy o áudio começa no ponto marcado, mas o vídeo só no
    próximo keyframe — gera 1–2s sem imagem no início do clip.
    """
    duration = max(0.05, end - start)
    # -ss antes de -i: seek rápido; com reencode o accurate_seek (padrão)
    # descarta frames até o ponto exato, mantendo A/V sincronizados.
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(source),
        "-t",
        f"{duration:.3f}",
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
        str(dest),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        # Fallback: -ss após -i (mais lento, ainda mais preciso em alguns containers)
        cmd_slow = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{duration:.3f}",
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
            str(dest),
        ]
        result2 = subprocess.run(cmd_slow, capture_output=True, text=True, check=False)
        if result2.returncode != 0:
            raise RuntimeError(
                result2.stderr.strip() or result.stderr.strip() or "FFmpeg falhou"
            )
