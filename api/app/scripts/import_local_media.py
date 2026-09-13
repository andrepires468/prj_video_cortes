"""Copia vídeos/cortes de data/ para MinIO + MySQL. Não apaga nem altera a pasta data/."""

from __future__ import annotations

import argparse
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.db import SessionLocal
from app.models.orm import Corte, Download, Usuario
from app.models.schemas import JobStatus
from app.services import s3
from app.services.filenames import safe_video_stem
from app.services.probe import probe_media
from app.services.thumbnail import generate_thumbnail_to

VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v"}

ANDRE_EMAIL = "andrepires468@gmail.com"
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _mtime_naive(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(tzinfo=None)


def _is_video(path: Path) -> bool:
    if not path.is_file() or path.name.startswith("."):
        return False
    if path.name.endswith((".part", ".ytdl", ".temp")):
        return False
    return path.suffix.lower() in VIDEO_EXTENSIONS


def _probe(path: Path):
    try:
        return probe_media(path)
    except Exception as exc:  # noqa: BLE001
        print(f"  aviso: probe falhou ({path.name}): {exc}")
        return None


def _upload_thumb(video: Path, key: str) -> str | None:
    local_jpg = video.with_suffix(".jpg")
    if local_jpg.is_file():
        s3.put_file(key, local_jpg)
        return key
    dest: Path | None = None
    try:
        handle = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        dest = Path(handle.name)
        handle.close()
        generate_thumbnail_to(video, dest)
        s3.put_file(key, dest)
        return key
    except Exception as exc:  # noqa: BLE001
        print(f"  aviso: thumb não gerada ({video.name}): {exc}")
        return None
    finally:
        if dest is not None and dest.exists():
            dest.unlink()


def _list_videos(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted((p for p in directory.iterdir() if _is_video(p)), key=lambda p: p.name.lower())


def run(downloads_dir: Path, cortes_dir: Path, email: str) -> int:
    db = SessionLocal()
    sent = skipped = errors = 0
    orphan_cortes = 0
    try:
        usuario = db.query(Usuario).filter(Usuario.email == email).one_or_none()
        if not usuario:
            print(f"Usuário não encontrado: {email}")
            return 1
        uid = usuario.id
        print(f"Usuário {usuario.nome} ({uid})")
        print(f"Downloads: {downloads_dir}")
        print(f"Cortes:    {cortes_dir}")

        videos = _list_videos(downloads_dir)
        claimed_cortes: set[str] = set()

        for video in videos:
            existing = (
                db.query(Download)
                .filter(Download.usuario_id == uid, Download.filename == video.name)
                .one_or_none()
            )
            if existing:
                print(f"pular download já importado: {video.name}")
                skipped += 1
                prefix = f"{safe_video_stem(video.name)}_corte_"
                for corte_path in _list_videos(cortes_dir):
                    if corte_path.stem.startswith(prefix):
                        claimed_cortes.add(corte_path.name)
                continue

            download_id = str(uuid.uuid4())
            storage_key = s3.download_object_key(uid, download_id, video.name)
            thumb_key = s3.download_thumb_key(uid, download_id, video.stem)
            try:
                print(f"enviar download: {video.name}")
                s3.put_file(storage_key, video)
                uploaded_thumb = _upload_thumb(video, thumb_key)
                info = _probe(video)
                mtime = _mtime_naive(video)
                row = Download(
                    id=download_id,
                    usuario_id=uid,
                    url_origem=f"local://data/downloads/{video.name}"[:2048],
                    storage_key=storage_key,
                    thumb_key=uploaded_thumb,
                    provider=None,
                    filename=video.name,
                    status=JobStatus.done,
                    progress=100.0,
                    mensagem="Importado do disco local",
                    tamanho_bytes=video.stat().st_size,
                    duracao_seg=info.duration if info else None,
                    largura=info.width if info else None,
                    altura=info.height if info else None,
                    erro=None,
                    criado_em=mtime,
                    atualizado_em=mtime,
                )
                db.add(row)
                db.flush()

                prefix = f"{safe_video_stem(video.name)}_corte_"
                for corte_path in _list_videos(cortes_dir):
                    if not corte_path.stem.startswith(prefix):
                        continue
                    claimed_cortes.add(corte_path.name)
                    already = (
                        db.query(Corte)
                        .filter(Corte.usuario_id == uid, Corte.filename == corte_path.name)
                        .one_or_none()
                    )
                    if already:
                        print(f"  pular corte já importado: {corte_path.name}")
                        skipped += 1
                        continue
                    corte_id = str(uuid.uuid4())
                    corte_key = s3.corte_object_key(uid, download_id, corte_id, corte_path.name)
                    corte_thumb = s3.corte_thumb_key(uid, download_id, corte_id, corte_path.stem)
                    print(f"  enviar corte: {corte_path.name}")
                    s3.put_file(corte_key, corte_path)
                    uploaded_corte_thumb = _upload_thumb(corte_path, corte_thumb)
                    corte_info = _probe(corte_path)
                    duration = (
                        corte_info.duration
                        if corte_info and corte_info.duration > 0
                        else (info.duration if info and info.duration > 0 else 0.0)
                    )
                    cmtime = _mtime_naive(corte_path)
                    db.add(
                        Corte(
                            id=corte_id,
                            download_id=download_id,
                            usuario_id=uid,
                            corte_origem_id=None,
                            storage_key=corte_key,
                            thumb_key=uploaded_corte_thumb,
                            filename=corte_path.name,
                            inicio_seg=0.0,
                            fim_seg=duration if duration > 0 else 0.001,
                            velocidade=1.0,
                            status=JobStatus.done,
                            progress=100.0,
                            mensagem="Importado do disco local",
                            tamanho_bytes=corte_path.stat().st_size,
                            erro=None,
                            criado_em=cmtime,
                            atualizado_em=cmtime,
                        )
                    )
                    sent += 1

                db.commit()
                sent += 1
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                errors += 1
                print(f"erro em {video.name}: {exc}")

        for corte_path in _list_videos(cortes_dir):
            if corte_path.name not in claimed_cortes:
                orphan_cortes += 1
                print(f"órfão (sem download): {corte_path.name} — não importado, arquivo local intacto")

        print(
            f"\nResumo: enviados={sent} pulados={skipped} erros={errors} orfaos_cortes={orphan_cortes}"
        )
        return 1 if errors else 0
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa data/ para MinIO e MySQL sem apagar o disco.")
    parser.add_argument(
        "--downloads-dir",
        type=Path,
        default=_REPO_ROOT / "data" / "downloads",
    )
    parser.add_argument(
        "--cortes-dir",
        type=Path,
        default=_REPO_ROOT / "data" / "cortes",
    )
    parser.add_argument("--email", default=ANDRE_EMAIL)
    args = parser.parse_args()
    if not settings.minio_endpoint or not settings.mysql_host:
        print("Configure MINIO_* e MYSQL_* em api/.env")
        sys.exit(1)
    raise SystemExit(run(args.downloads_dir, args.cortes_dir, args.email))


if __name__ == "__main__":
    main()
