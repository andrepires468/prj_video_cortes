from __future__ import annotations

import re
import unicodedata
from pathlib import Path


def remove_special_chars(name: str) -> str:
    """Remove caracteres especiais; espaços viram underline; mantém letras, números, _ e -."""
    text = (name or "").strip()
    if not text:
        return ""

    # Normaliza e remove acentos (ex.: ç→c, á→a)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))

    text = text.replace(" ", "_")
    # Remove tudo que não for alfanumérico, underline ou hífen
    text = re.sub(r"[^A-Za-z0-9_-]+", "", text)
    # Colapsa underlines repetidos
    text = re.sub(r"_+", "_", text)
    text = text.strip("_-")
    return text


def safe_video_stem(name: str) -> str:
    """Stem sanitizado usado nos nomes de corte ({stem}_corte_01.mp4)."""
    stem = remove_special_chars(Path(name).stem)
    return stem[:80] if stem else "clip"


def build_video_filename(title: str, video_id: str, ext: str) -> str:
    """
    Monta nome final do download:
    {titulo_sanitizado}_{codigo}.{ext_minuscula}
    """
    base = remove_special_chars(title) or "video"
    code = remove_special_chars(video_id) or "unknown"
    # Evita duplicar o código se o título já terminar com ele
    if base.lower().endswith(f"_{code.lower()}"):
        stem = base
    else:
        stem = f"{base}_{code}"

    ext_clean = (ext or "mp4").lstrip(".").lower()
    return f"{stem}.{ext_clean}"
