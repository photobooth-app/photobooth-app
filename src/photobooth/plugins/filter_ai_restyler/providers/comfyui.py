import io
import json
import random
import time
import uuid

import requests
from PIL import Image

from ..config import ComfyUIProviderConfig
from .base import BaseProvider, ProviderError

POLL_INTERVAL = 0.25


def fill_placeholders(node, values: dict[str, str | int]):
    """replaces {{key}} placeholders in all strings of the workflow. If a string consists of a placeholder only, the value keeps its type."""
    if isinstance(node, dict):
        return {k: fill_placeholders(v, values) for k, v in node.items()}
    if isinstance(node, list):
        return [fill_placeholders(v, values) for v in node]
    if isinstance(node, str):
        for key, value in values.items():
            placeholder = f"{{{{{key}}}}}"
            if node == placeholder:
                return value
            node = node.replace(placeholder, str(value))
    return node


class ComfyuiProvider(BaseProvider):
    def __init__(self, config: ComfyUIProviderConfig):
        if not config.workflow_file:
            raise ProviderError("no ComfyUI workflow file configured")

        self._config = config
        self._base_url = str(config.base_url).rstrip("/")
        self._session = requests.Session()
        if config.api_key.get_secret_value():
            self._session.headers["Authorization"] = f"Bearer {config.api_key.get_secret_value()}"

        try:
            self._workflow = json.loads(config.workflow_file.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ProviderError(f"cannot load ComfyUI workflow {config.workflow_file}: {exc}") from exc

    @property
    def cache_identifier(self) -> str:
        return f"comfyui:{self._base_url}:{json.dumps(self._workflow, sort_keys=True)}"

    def restyle(self, jpeg: bytes, prompt: str, negative_prompt: str) -> Image.Image:
        cfg = self._config
        deadline = time.monotonic() + cfg.timeout
        client_id = uuid.uuid4().hex

        r = self._session.post(
            f"{self._base_url}/upload/image",
            files={"image": (f"photobooth_{client_id}.jpg", jpeg, "image/jpeg")},
            data={"overwrite": "true"},
            timeout=cfg.timeout,
        )
        if not r.ok:
            raise ProviderError(f"ComfyUI image upload failed with status {r.status_code}: {r.text[:300]}")
        uploaded = r.json()
        image_name = f"{uploaded['subfolder']}/{uploaded['name']}" if uploaded.get("subfolder") else uploaded["name"]

        workflow = fill_placeholders(
            self._workflow,
            {"image": image_name, "prompt": prompt, "negative_prompt": negative_prompt, "seed": random.randint(0, 2**32 - 1)},
        )

        r = self._session.post(f"{self._base_url}/prompt", json={"prompt": workflow, "client_id": client_id}, timeout=cfg.timeout)
        if not r.ok:
            raise ProviderError(f"ComfyUI rejected the workflow with status {r.status_code}: {r.text[:300]}")
        prompt_id = r.json()["prompt_id"]

        while True:
            r = self._session.get(f"{self._base_url}/history/{prompt_id}", timeout=cfg.timeout)
            r.raise_for_status()
            history = r.json().get(prompt_id)

            if history:
                status = history.get("status", {})
                if status.get("status_str") == "error":
                    raise ProviderError(f"ComfyUI workflow failed: {str(status.get('messages'))[:300]}")
                if status.get("completed", True):
                    return self._download_first_output(history)

            if time.monotonic() > deadline:
                self._interrupt()
                raise ProviderError(f"ComfyUI did not finish within {cfg.timeout}s")

            time.sleep(POLL_INTERVAL)

    def _download_first_output(self, history: dict) -> Image.Image:
        for node_output in history.get("outputs", {}).values():
            for img in node_output.get("images", []):
                if img.get("type", "output") != "output":
                    continue
                r = self._session.get(
                    f"{self._base_url}/view",
                    params={"filename": img["filename"], "subfolder": img.get("subfolder", ""), "type": "output"},
                    timeout=self._config.timeout,
                )
                r.raise_for_status()
                image = Image.open(io.BytesIO(r.content))
                image.load()
                return image

        raise ProviderError("ComfyUI workflow produced no output image. Make sure the workflow contains a SaveImage node.")

    def _interrupt(self):
        try:
            self._session.post(f"{self._base_url}/interrupt", timeout=5)
        except Exception:
            pass
