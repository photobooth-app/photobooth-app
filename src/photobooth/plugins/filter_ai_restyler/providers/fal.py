import requests
from PIL import Image

from ..config import FalProviderConfig
from .base import BaseProvider, ProviderError, load_image_from_uri, parse_params, to_data_uri


class FalProvider(BaseProvider):
    def __init__(self, config: FalProviderConfig):
        if not config.api_key.get_secret_value():
            raise ProviderError("fal.ai API key is missing")

        self._config = config

    @property
    def cache_identifier(self) -> str:
        return f"fal:{self._config.model_id}"

    def restyle(self, jpeg: bytes, prompt: str, negative_prompt: str) -> Image.Image:
        cfg = self._config
        payload = {
            **parse_params(cfg.extra_params),
            "prompt": prompt,
            cfg.image_param_name: [to_data_uri(jpeg)] if cfg.image_param_as_list else to_data_uri(jpeg),
            "num_images": 1,
            "sync_mode": True,
        }

        r = requests.post(
            f"{str(cfg.base_url).rstrip('/')}/{cfg.model_id}",
            json=payload,
            headers={"Authorization": f"Key {cfg.api_key.get_secret_value()}"},
            timeout=cfg.timeout,
        )
        if not r.ok:
            raise ProviderError(f"fal.ai request failed with status {r.status_code}: {r.text[:300]}")

        result = r.json()
        if any(result.get("has_nsfw_concepts") or []):
            raise ProviderError("fal.ai flagged the result as NSFW")

        try:
            url = result["images"][0]["url"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"unexpected fal.ai response: {str(result)[:300]}") from exc

        return load_image_from_uri(url, cfg.timeout)
