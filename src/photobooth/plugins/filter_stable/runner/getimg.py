import base64
import io
from io import BytesIO

import requests
from PIL import Image

from ..sdpresets.basefiltersd import BaseFilterSD
from .baserunner import BaseRunner


class GetImgAIFilter(BaseRunner):
    def __init__(self, api_key: str):
        super().__init__(api_key=api_key)

    def run(self, filter_preset: BaseFilterSD, image: Image.Image) -> Image.Image:
        buffered = BytesIO()
        size = 1024, 1024
        image.thumbnail(size, Image.Resampling.LANCZOS)
        image.save(buffered, format="JPEG")

        img_str = base64.b64encode(buffered.getvalue())
        url = "https://api.getimg.ai/v1/stable-diffusion/controlnet"

        payload = {
            "response_format": "b64",
            "steps": 40,
            "strength": 2.5,
            "width": filter_preset.width,
            "height": filter_preset.height,
            "image": img_str.decode("utf-8"),
            "prompt": filter_preset.prompt,
            "model": "dream-shaper-v8",
            "controlnet": "normal-1.1",
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {self.api_key}",
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()

            json_response: dict = response.json()
            # print(json_response.keys())

            filtered_image = json_response.get("image")
            if not filtered_image:
                raise RuntimeError("did not receive image from service")

        except requests.HTTPError as exc:
            print(exc)
            # logger.error(exc)
            raise RuntimeError(f"error processing the filter, error {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"error processing the filter, error {exc}") from exc

        else:
            image = Image.open(io.BytesIO(base64.b64decode(filtered_image)))

            return image
