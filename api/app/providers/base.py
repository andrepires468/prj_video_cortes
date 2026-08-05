from collections.abc import Callable
from pathlib import Path
from typing import Protocol


ProgressCallback = Callable[[float, str], None]


class DownloadProvider(Protocol):
    def can_handle(self, url: str) -> bool:
        """Return True if this provider can download the given URL."""

    def download(
        self,
        url: str,
        dest_dir: Path,
        progress_cb: ProgressCallback | None = None,
    ) -> Path:
        """Download media to dest_dir and return the resulting file path."""
