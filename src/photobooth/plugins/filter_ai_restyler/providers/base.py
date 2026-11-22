import base64
import io
import json
from abc import ABC, abstractmethod

import numpy as np
import requests
import simplejpeg
from PIL import Image

from ..config import ProviderParameter


class ProviderError(RuntimeError):
    pass


def encode_jpeg(image: Image.Image, quality: int = 90) -> bytes:
    jpeg_image = image if image.mode in ("RGB", "RGBA") else image.convert("RGB")
    return simplejpeg.encode_jpeg(np.asarray(jpeg_image), quality=quality, colorspace=jpeg_image.mode, colorsubsampling="420", fastdct=True)


def to_data_uri(jpeg: bytes) -> str:
    return f"data:image/jpeg;base64,{base64.b64encode(jpeg).decode('ascii')}"


def parse_params(params: list[ProviderParameter]) -> dict:
    out = {}
    for param in params:
        try:
            out[param.key] = json.loads(param.value)
        except ValueError:
            out[param.key] = param.value
    return out


def load_image_from_uri(uri: str, timeout: float, session: requests.Session | None = None) -> Image.Image:
    if uri.startswith("data:"):
        _, encoded = uri.split(",", 1)
        data = base64.b64decode(encoded)
    else:
        r = (session or requests).get(uri, timeout=timeout)
        r.raise_for_status()
        data = r.content

    image = Image.open(io.BytesIO(data))
    image.load()
    return image


class BaseProvider(ABC):
    @property
    @abstractmethod
    def cache_identifier(self) -> str:
        """identifies provider and model so cached results of different models are not mixed up"""

    @abstractmethod
    def restyle(self, jpeg: bytes, prompt: str, negative_prompt: str) -> Image.Image:
        """send the already encoded JPEG to the provider and return the restyled image"""
