import base64
import io
import json
from io import BytesIO
from pydoc import locate
from re import sub
import logging
from PIL import Image

from .filterpresets_sd import *
logger = logging.getLogger(__name__)

class StabilityAIFilter:
    def __init__(self, filter: str) -> None:
        self.filter = filter

    def __call__(self, params, image: Image.Image) -> Image.Image:
        try:
           
            import requests

            buffered = BytesIO()
            size = 1024, 1024
            image.thumbnail(size, Image.Resampling.LANCZOS)
            image.save(buffered, format="JPEG")

            img_str = base64.b64encode(buffered.getvalue())
            img_str = img_str.decode("ascii")

            url = "https://api.stability.ai/v2beta/stable-image/control/structure"
            apikey = ""
            headers={
                "authorization": "Bearer " + apikey,
                "accept": "image/*"
            }
            payload = {
                "control_strength" : params["denoising_strength"],
                "seed" : 0,
                "output_format": "jpeg",
                "prompt" : params["prompt"],
                "negative_prompt" : params["negative_prompt"],
            }
            
            response = requests.post(url, files={
                    "image": buffered.getvalue()
            }, data=payload, headers=headers)

            logger.debug( "Response from Stability.ai: " + repr(response))
            image = Image.open(io.BytesIO(response.content))
            return image

        except Exception as exc:
            logger.debug( "Error  processing the request from Stability.ai: " + repr ( response))
            raise RuntimeError(f"error processing the filter {self.filter}") from exc

    def __repr__(self) -> str:
        return self.__class__.__name__


def to_camelcase(s):
    s = sub(r"(_|-)+", " ", s).title().replace(" ", "").replace("*", "")
    return "".join([s[0].upper(), s[1:]])


def merge_nested_dicts(dict1, dict2):
    res = {}
    for key, value in dict1.items():
        if key in dict2:
            res[key] = merge_nested_dicts(dict1[key], dict2[key])
            del dict2[key]
        else:
            res[key] = value
    res.update(dict2)
    return res
