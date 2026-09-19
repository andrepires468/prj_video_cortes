"""Redimensiona thumbs já gravadas no MinIO (teto 320×320) e guarda backup `*_bkp.jpg`.

Não altera MySQL (`thumb_key` continua o mesmo).

  python -m app.scripts.resize_stored_thumbs
  python -m app.scripts.resize_stored_thumbs --apply
  python -m app.scripts.resize_stored_thumbs --restore
  python -m app.scripts.resize_stored_thumbs --purge-backups
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.db import SessionLocal
from app.models.orm import Corte, Download
from app.services import s3
from app.services.probe import probe_media
from app.services.thumbnail import image_fits_thumb_limit, resize_thumbnail_image


@dataclass(frozen=True)
class ThumbJob:
    origem: str
    row_id: str
    filename: str | None
    thumb_key: str


def _collect_jobs(db) -> list[ThumbJob]:
    jobs: list[ThumbJob] = []
    for row in db.query(Download).filter(Download.thumb_key.isnot(None)).all():
        key = (row.thumb_key or "").strip()
        if not key:
            continue
        jobs.append(ThumbJob("download", row.id, row.filename, key))
    for row in db.query(Corte).filter(Corte.thumb_key.isnot(None)).all():
        key = (row.thumb_key or "").strip()
        if not key:
            continue
        jobs.append(ThumbJob("corte", row.id, row.filename, key))
    return jobs


def _work_one(
    job: ThumbJob,
    work_dir: Path,
    restore: bool,
    apply: bool,
    purge_backups: bool,
) -> str:
    key = job.thumb_key
    backup_key = s3.thumb_backup_key(key)
    label = f"{job.origem} {job.filename or job.row_id}"

    if backup_key == key:
        print(f"pular (já é backup): {key}")
        return "skip"

    if purge_backups:
        if not backup_key.endswith("_bkp.jpg"):
            print(f"pular (chave de backup inválida): {backup_key}")
            return "skip"
        if not s3.object_exists(backup_key):
            print(f"sem backup: {label}")
            return "skip"
        print(f"apagar backup: {backup_key}")
        s3.remove_object(backup_key)
        return "ok"

    if not s3.object_exists(key):
        print(f"ausente no storage: {label} ({key})")
        return "missing"

    if restore:
        if not s3.object_exists(backup_key):
            print(f"sem backup: {label}")
            return "skip"
        print(f"{'restaurar' if apply else 'restauraria'}: {backup_key} → {key}")
        if apply:
            s3.copy_object(backup_key, key)
        return "ok"

    src = work_dir / f"{job.origem}_{job.row_id}.jpg"
    s3.get_file(key, src)
    info = probe_media(src)
    already_ok = image_fits_thumb_limit(info.width, info.height)
    backup_exists = s3.object_exists(backup_key)

    if already_ok:
        print(
            f"já cabe ({info.width}x{info.height}, {info.size} B): {label}"
            + (" [backup ok]" if backup_exists else "")
        )
        return "skip"

    print(
        f"{'atualizar' if apply else 'atualizaria'} "
        f"{info.width}x{info.height} {info.size} B → 320×320: {label}"
    )
    print(f"  origem: {key}")
    print(f"  backup: {backup_key}{' (já existe, não sobrescreve)' if backup_exists else ''}")

    if not apply:
        return "ok"

    if not backup_exists:
        s3.copy_object(key, backup_key)

    dest = src.with_name(f"{src.stem}_resized.jpg")
    resize_thumbnail_image(src, dest)
    s3.put_file(key, dest)
    return "ok"


def run(*, apply: bool, restore: bool, purge_backups: bool, limit: int | None) -> int:
    if not settings.minio_endpoint or not settings.mysql_host:
        print("Configure MINIO_* e MYSQL_* em api/.env")
        return 1

    if purge_backups:
        mode = "PURGE-BACKUPS"
    elif restore:
        mode = "RESTORE"
    elif apply:
        mode = "APPLY"
    else:
        mode = "DRY-RUN"
    print(f"Modo: {mode} | bucket={settings.minio_bucket}")
    if not apply and not restore and not purge_backups:
        print("Nenhum objeto será gravado. Use --apply (ou --restore / --purge-backups) para escrever no MinIO.\n")

    db = SessionLocal()
    ok = skip = missing = errors = 0
    try:
        jobs = _collect_jobs(db)
        if limit is not None:
            jobs = jobs[: max(0, limit)]
        print(f"Thumbs no banco: {len(jobs)}\n")
        with tempfile.TemporaryDirectory(prefix="vc-thumbs-") as tmp:
            work_dir = Path(tmp)
            for job in jobs:
                try:
                    status = _work_one(
                        job,
                        work_dir,
                        restore=restore,
                        apply=apply,
                        purge_backups=purge_backups,
                    )
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    print(f"erro: {job.origem} {job.filename or job.row_id}: {exc}")
                    continue
                if status == "ok":
                    ok += 1
                elif status == "missing":
                    missing += 1
                else:
                    skip += 1
    finally:
        db.close()

    print(
        f"\nResumo: {'feitos' if (apply or restore or purge_backups) else 'previstos'}={ok} "
        f"pulados={skip} ausentes={missing} erros={errors}"
    )
    return 1 if errors else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backup *_bkp.jpg e redimensiona thumbs no MinIO (teto 320×320)."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Grava no MinIO: copia backup e substitui a thumb original.",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Copia cada *_bkp.jpg de volta para a thumb original (não apaga o backup).",
    )
    parser.add_argument(
        "--purge-backups",
        action="store_true",
        help="Apaga só os *_bkp.jpg no MinIO. Não mexe nas thumbs atuais.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Processa só N thumbs (teste).")
    args = parser.parse_args()
    exclusive = [args.apply, args.restore, args.purge_backups]
    if sum(bool(flag) for flag in exclusive) > 1:
        print("Use só um de: --apply, --restore, --purge-backups.")
        sys.exit(1)
    raise SystemExit(
        run(
            apply=args.apply,
            restore=args.restore,
            purge_backups=args.purge_backups,
            limit=args.limit,
        )
    )


if __name__ == "__main__":
    main()
