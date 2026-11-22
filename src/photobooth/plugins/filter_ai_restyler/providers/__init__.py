from ..config import ComfyUIProviderConfig, FalProviderConfig, ProviderConfig, ReplicateProviderConfig
from .base import BaseProvider, ProviderError
from .comfyui import ComfyuiProvider
from .fal import FalProvider
from .replicate import ReplicateProvider

__all__ = ["BaseProvider", "ProviderError", "create_provider"]


def create_provider(config: ProviderConfig) -> BaseProvider:
    if isinstance(config, FalProviderConfig):
        return FalProvider(config)
    if isinstance(config, ReplicateProviderConfig):
        return ReplicateProvider(config)
    if isinstance(config, ComfyUIProviderConfig):
        return ComfyuiProvider(config)

    raise ProviderError(f"unknown provider {config}")
