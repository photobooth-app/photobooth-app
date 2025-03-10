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
        img_bytesio = BytesIO()
        size = (1024, 1024)
        image.thumbnail(size, Image.Resampling.LANCZOS)
        image.save(img_bytesio, format="JPEG")

        url = "https://api.getimg.ai/v1/stable-diffusion/controlnet"
        # url = "https://api.getimg.ai/v1/stable-diffusion/image-to-image"
        # print(filter_preset)
        # print(filter_preset.prompt)
        payload = {
            "response_format": "b64",
            "steps": 40,
            "strength": 0.5,
            "width": 768,
            "height": 512,
            "image": base64.b64encode(img_bytesio.getvalue()).decode("ascii"),
            "prompt": filter_preset.prompt,
            "model": "dream-shaper-v8",
            "sampler": "DPM++ 2M SDE Karras",
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
            raise RuntimeError(f"error processing the filter, error {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"error processing the filter, error {exc}") from exc

        else:
            image = Image.open(io.BytesIO(base64.b64decode(filtered_image)))

            return image
