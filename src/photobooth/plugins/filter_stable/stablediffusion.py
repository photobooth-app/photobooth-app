from pydoc import locate
from re import sub

from PIL import Image
from webuiapi import *

from .sdpresets.basefiltersd import BaseFilterSD
from .sdpresets.filterpresets_sd import *

# ! stable-diffusion models needed
#  absolutereality181.n8IR.safetensors [463d6a9fe8]
#  animepasteldreamSoft.lTTK.safetensors [4be38c1a17]
#  caricaturizer_pcrc_style.uwgn1lmj.q5b.ckpt
#  clazy2600.xYzn.ckpt [ed2cf308d1]
#  dreamshaper8Pruned.hz5Q.safetensors [879db523c3]
#  v1-5-pruned-emaonly.safetensors [6ce0161689]
#  westernanidiffusion.EpVW.safetensors [d20bc9d543]


# ! lora needed
#  "ClayAnimationRedmond15-ClayAnimation-Clay"
#  "coolkidsMERGEV25.Qqci"
#  "gotchaV001.Yu4Z"
#  "neotokioV001.yBGi"
#  "stylizardV1.mPLw"
#  "watercolorv1.7lox"


class StableDiffusionFilter:
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
            api = WebUIApi(host="192.168.78.76", port=7860)
            options = {}
            options["sd_model_checkpoint"] = params["model"]

            api.set_options(options)
            params.pop("model", None)

            controlnets = []
            openpose = ControlNetUnit(
                module=params["openpose"]["module"],
                model=params["openpose"]["model"],
                weight=params["openpose"]["weight"],
                threshold_a=0.5,
                threshold_b=0.5,
                resize_mode="Crop and Resize",
            )
            # openpose.input_mode = "simple"
            # openpose.save_detected_map=True
            # openpose.use_preview_as_input= False,
            params.pop("openpose", None)
            controlnets.append(openpose)

            depth = ControlNetUnit(
                module=params["depth"]["module"],
                model=params["depth"]["model"],
                weight=params["depth"]["weight"],
                threshold_a=0.5,
                threshold_b=0.5,
                resize_mode="Crop and Resize",
            )
            controlnets.append(depth)
            params.pop("depth", None)

            softedge = ControlNetUnit(
                module=params["softedge"]["module"],
                model=params["softedge"]["model"],
                weight=params["softedge"]["weight"],
                threshold_a=0.5,
                threshold_b=0.5,
                resize_mode="Crop and Resize",
            )
            controlnets.append(softedge)

            params.pop("softedge", None)

            params["controlnet_units"] = controlnets
            params["images"] = [image]
            params["negative_prompt"] = str(params["negative_prompt"][0])
            params["seed"] = int(params["seed"][0])
            params["batch_size"] = int(params["batch_size"][0])
            params["steps"] = int(params["steps"][0])
            params["height"] = int(params["height"][0])
            params["width"] = int(params["width"][0])
            params["sampler_index"] = ""
            params["denoising_strength"] = float(params["denoising_strength"][0])
            params["cfg_scale"] = float(params["cfg_scale"][0])
            result = api.img2img(**params)
            # for x in params["images"]:
            #    print( b64_img(x))
            # print( repr(params) )
            return result.image

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
