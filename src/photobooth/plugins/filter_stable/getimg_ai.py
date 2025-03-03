import base64
import io
import json
from io import BytesIO
from pydoc import locate
from re import sub

from PIL import Image

from .sdpresets.basefiltersd import BaseFilterSD
from .sdpresets.filterpresets_sd import *


class GetImgAIFilter:
    def __init__(self, filter: str) -> None:
        self.filter = filter

    def __call__(self, filter: str, image: Image.Image) -> Image.Image:
        try:
            baseparams = {
                key: value
                for key, value in BaseFilterSD.__dict__.items()
                if not key.startswith("__") and not callable(value) and not callable(getattr(value, "__get__", None))
            }
            filterclass = to_camelcase(filter)
            # e.g. for style "anime" import AnimeFilterSD
            mod = locate("photobooth.filters.sdpresets.filterpresets_sd." + filterclass + "FilterSD")
            sdfilter = mod()
            filterparams = sdfilter.getParams()
            # Combine the Base Paramters and the special filter parameters

            params = merge_nested_dicts(baseparams, filterparams)

            # create API client with custom host, port
            # TODO: create configuration parameters
            # api = webuiapi.WebUIApi(host="127.0.0.1", port=7860)
            import requests

            buffered = BytesIO()
            size = 1024, 1024
            image.thumbnail(size, Image.Resampling.LANCZOS)
            image.save(buffered, format="JPEG")

            img_str = base64.b64encode(buffered.getvalue())
            url = "https://api.getimg.ai/v1/stable-diffusion/controlnet"
            # In tests it proved to be useful to add the following to the prompt:
            params["prompt"] += (
                ", energetic atmosphere capturing thrill of the moment, clear details, best quality, extremely detailed cg 8k wallpaper, volumetric lighting, 4k, best quality, masterpiece, ultrahigh res, group photo, sharp focus, (perfect image composition)"
            )
            payload = {
                "response_format": "b64",
                "steps": 40,
                "strength": 2.5,
                "width": params["width"],
                "height": params["height"],
                "image": img_str.decode("utf-8"),
                "prompt": params["prompt"],
                "model": "dream-shaper-v8",
                "controlnet": "normal-1.1",
            }
            headers = {"accept": "application/json", "content-type": "application/json", "authorization": "Bearer key-xxxxx"}

            response = requests.post(url, json=payload, headers=headers)
            json_response = json.loads(response.text)
            # print( repr(json_response))
            image = Image.open(io.BytesIO(base64.b64decode(json_response["image"])))
            return image

            # optionally set username, password when --api-auth=username:password is set on webui.
            # username, password are not protected and can be derived easily if the communication channel is not encrypted.
            # you can also pass username, password to the WebUIApi constructor.
            # api.set_auth('username', 'password')

        except Exception as exc:
            raise PipelineError(f"error processing the filter {self.filter}") from exc

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
