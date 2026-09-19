from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.db import SessionLocal
from app.models.orm import Corte, Download
from app.models.schemas import CutJobInfo, CutSegment, JobStatus
from app.services import library, s3
from app.services.filenames import safe_video_stem
from app.services.probe import probe_media
from app.services.thumbnail import generate_thumbnail_to

_lock = threading.Lock()
_jobs: dict[str, CutJobInfo] = {}

SPEED_MIN = 0.25
SPEED_MAX = 2.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_naive() -> datetime:
    return _now().replace(tzinfo=None)


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


def _source_from_library(
    download_id: str,
    source_corte_id: str | None,
    usuario_id: str,
) -> tuple[Download, str, str, float, str | None]:
    db = SessionLocal()
    try:
        download = library.get_download_by_id(db, download_id, usuario_id)
        if not download or not download.storage_key or not download.filename:
            raise ValueError("Arquivo não encontrado")
        duration = float(download.duracao_seg or 0)
        source_key = download.storage_key
        source_name = download.filename
        corte_origem_id = None
        if source_corte_id:
            origem = library.get_corte_by_id(db, source_corte_id, usuario_id)
            if (
                not origem
                or origem.download_id != download.id
                or not origem.storage_key
                or not origem.filename
            ):
                raise ValueError("O arquivo informado não é um corte deste vídeo.")
            source_key = origem.storage_key
            source_name = origem.filename
            corte_origem_id = origem.id
            cut_duration = float((origem.fim_seg or 0) - (origem.inicio_seg or 0))
            if cut_duration > 0:
                duration = cut_duration
        return download, source_key, source_name, duration, corte_origem_id
    finally:
        db.close()


def create_cut_job(
    download_id: str,
    markers: list[float],
    usuario_id: str,
    segments: list[CutSegment] | None = None,
    speed: float = 1.0,
    source_corte_id: str | None = None,
) -> CutJobInfo:
    download, source_key, source_name, duration, corte_origem_id = _source_from_library(
        download_id, source_corte_id, usuario_id
    )

    if segments:
        max_end = duration if duration > 0 else max(s.end for s in segments)
        resolved = [
            CutSegment(start=max(0.0, s.start), end=min(max_end, s.end) if max_end else s.end)
            for s in segments
            if s.end > s.start
        ]
    else:
        if duration <= 0:
            raise ValueError("Duração do vídeo inválida")
        resolved = markers_to_segments(markers, duration)

    if not resolved:
        raise ValueError("Nenhum segmento válido para exportar.")

    job_id = str(uuid.uuid4())
    job = CutJobInfo(
        id=job_id,
        status=JobStatus.queued,
        progress=0.0,
        message="Na fila",
        filename=download.filename or download_id,
        outputs=[],
        created_at=_now(),
        updated_at=_now(),
    )
    with _lock:
        _jobs[job_id] = job

    thread = threading.Thread(
        target=_run_cuts,
        args=(
            job_id,
            download.id,
            usuario_id,
            source_key,
            source_name,
            download.filename or download_id,
            resolved,
            _clamp_speed(speed),
            corte_origem_id,
        ),
        daemon=True,
    )
    thread.start()
    return job


def _safe_stem(name: str) -> str:
    return safe_video_stem(name)


def _cut_out_name(download_id: str, stem: str, index: int) -> str:
    db = SessionLocal()
    try:
        names = {
            row[0]
            for row in db.query(Corte.filename).filter(Corte.download_id == download_id)
            if row[0]
        }
    finally:
        db.close()
    ext = ".mp4"
    name = f"{stem}_corte_{index:02d}{ext}"
    counter = 1
    while name in names:
        counter += 1
        name = f"{stem}_corte_{index:02d}_{counter}{ext}"
    return name[:255]


def _run_cuts(
    job_id: str,
    download_id: str,
    usuario_id: str,
    source_key: str,
    source_name: str,
    output_filename: str,
    segments: list[CutSegment],
    speed: float,
    corte_origem_id: str | None,
) -> None:
    _update_job(job_id, status=JobStatus.running, message="Exportando cortes…", progress=0.0)
    outputs: list[str] = []
    work = Path(tempfile.mkdtemp(prefix="vc-cut-"))
    stem = _safe_stem(output_filename)

    try:
        source = s3.get_file(source_key, work / source_name)
        total = len(segments)
        for index, segment in enumerate(segments, start=1):
            out_name = _cut_out_name(download_id, stem, index)
            out_path = work / out_name
            corte_id = str(uuid.uuid4())

            _update_job(
                job_id,
                message=f"Exportando corte {index}/{total}…",
                progress=round((index - 1) / total * 80, 1),
            )
            _ffmpeg_cut(source, out_path, segment.start, segment.end, speed)

            thumb_path = None
            try:
                thumb_path = generate_thumbnail_to(out_path, out_path.with_suffix(".jpg"))
            except Exception:  # noqa: BLE001 — corte ok mesmo se thumb falhar
                pass

            _update_job(job_id, message="Enviando ao storage…", progress=round((index - 0.2) / total * 100, 1))
            storage_key = s3.corte_object_key(usuario_id, download_id, corte_id, out_name)
            s3.put_file(storage_key, out_path)
            thumb_key = None
            if thumb_path is not None and thumb_path.is_file():
                thumb_key = s3.corte_thumb_key(usuario_id, download_id, corte_id, Path(out_name).stem)
                s3.put_file(thumb_key, thumb_path)

            info = None
            try:
                info = probe_media(out_path)
            except Exception:  # noqa: BLE001
                info = None

            now = _now_naive()
            db = SessionLocal()
            try:
                row = Corte(
                    id=corte_id,
                    download_id=download_id,
                    usuario_id=usuario_id,
                    corte_origem_id=corte_origem_id,
                    storage_key=storage_key,
                    thumb_key=thumb_key,
                    filename=out_name,
                    inicio_seg=float(segment.start),
                    fim_seg=float(segment.end),
                    velocidade=speed,
                    status=JobStatus.done,
                    progress=100.0,
                    mensagem="Corte concluído",
                    tamanho_bytes=out_path.stat().st_size if out_path.is_file() else (info.size if info else None),
                    criado_em=now,
                    atualizado_em=now,
                )
                db.add(row)
                db.commit()
            except Exception:
                db.rollback()
                s3.remove_object(storage_key)
                s3.remove_object(thumb_key)
                raise
            finally:
                db.close()

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
    finally:
        shutil.rmtree(work, ignore_errors=True)


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
    """Corte com reencode (não usa -c copy). Velocidade altera só o arquivo gerado."""
    duration = max(0.05, end - start)
    speed = _clamp_speed(speed)
    speed_args = _speed_filter_args(speed)

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
