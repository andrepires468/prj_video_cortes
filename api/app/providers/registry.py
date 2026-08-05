from app.providers.base import DownloadProvider
from app.providers.x import XProvider
from app.providers.youtube import YoutubeProvider

# Ordem importa: o primeiro que aceitar a URL é usado
_providers: list[DownloadProvider] = [
    YoutubeProvider(),
    XProvider(),
]


def get_provider(url: str) -> DownloadProvider:
    for provider in _providers:
        if provider.can_handle(url):
            return provider
    raise ValueError(
        "URL não suportada. Aceitos: YouTube e X (Twitter)."
    )


def register_provider(provider: DownloadProvider) -> None:
    """Allow future platforms to register additional download providers."""
    _providers.append(provider)
