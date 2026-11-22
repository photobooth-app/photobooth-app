import time

import requests
from PIL import Image

from ..config import ReplicateProviderConfig
from .base import BaseProvider, ProviderError, load_image_from_uri, parse_params, to_data_uri

POLL_INTERVAL = 0.25


class ReplicateProvider(BaseProvider):
    def __init__(self, config: ReplicateProviderConfig):
        if not config.api_key.get_secret_value():
            raise ProviderError("Replicate API token is missing")

        self._config = config

    @property
    def cache_identifier(self) -> str:
        return f"replicate:{self._config.model_id}"

    def restyle(self, jpeg: bytes, prompt: str, negative_prompt: str) -> Image.Image:
        cfg = self._config
        deadline = time.monotonic() + cfg.timeout
        base_url = str(cfg.base_url).rstrip("/")
        headers = {"Authorization": f"Bearer {cfg.api_key.get_secret_value()}"}

        body: dict = {
            "input": {
                **parse_params(cfg.extra_params),
                "prompt": prompt,
                cfg.image_param_name: to_data_uri(jpeg),
            }
        }
        if ":" in cfg.model_id:
            # community models need to be addressed by version
            url = f"{base_url}/predictions"
            body["version"] = cfg.model_id.split(":", 1)[1]
        else:
            url = f"{base_url}/models/{cfg.model_id}/predictions"

        r = requests.post(
            url,
            json=body,
            headers=headers | {"Prefer": f"wait={max(1, min(60, int(cfg.timeout)))}"},
            timeout=cfg.timeout,
        )
        if not r.ok:
            raise ProviderError(f"Replicate request failed with status {r.status_code}: {r.text[:300]}")
        prediction = r.json()

        while prediction.get("status") in ("starting", "processing"):
            if time.monotonic() > deadline:
                self._cancel(prediction, headers)
                raise ProviderError(f"Replicate prediction did not finish within {cfg.timeout}s")

            time.sleep(POLL_INTERVAL)
            r = requests.get(prediction["urls"]["get"], headers=headers, timeout=cfg.timeout)
            r.raise_for_status()
            prediction = r.json()

        if prediction.get("status") != "succeeded":
            raise ProviderError(f"Replicate prediction {prediction.get('status')}: {prediction.get('error')}")

        output = prediction.get("output")
        if isinstance(output, list):
            output = output[0] if output else None
        if not isinstance(output, str):
            raise ProviderError(f"unexpected Replicate output: {str(output)[:300]}")

        return load_image_from_uri(output, cfg.timeout)

    def _cancel(self, prediction: dict, headers: dict):
        try:
            requests.post(prediction["urls"]["cancel"], headers=headers, timeout=5)
        except Exception:
            pass
