import webuiapi

from ..services.mediaprocessing.context import ImageContext
from ..utils.exceptions import PipelineError

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

    def __call__(self, filter: str, context: ImageContext) -> None:
        try:
            baseparams = {
                key: value
                for key, value in BaseFilterSD.__dict__.items()
                if not key.startswith("__") and not callable(value) and not callable(getattr(value, "__get__", None))
            }
            sdfilter = __import__("filterpresets_sd")
            filterparams = sdfilter.getParams()
            # Combine the Base Paramters and the special filter paramters
            params = {**baseparams, **filterparams}

            # create API client with custom host, port
            # TODO: create configuration parameters
            api = webuiapi.WebUIApi(host="127.0.0.1", port=7860)
            controlnets = []
            openpose = ControlNetUnit(
                module=params.Controlnet["openpose"]["module"],
                model=params.Controlnet["openpose"]["model"],
                weight=params.Controlnet["openpose"]["weight"],
            )
            controlnets.append(openpose)

            depth = ControlNetUnit(
                module=params.Controlnet["depth"]["module"], model=params.Controlnet["depth"]["model"], weight=params.Controlnet["depth"]["weight"]
            )
            controlnets.append(depth)

            softedge = ControlNetUnit(
                module=params.Controlnet["softedge"]["module"],
                model=params.Controlnet["softedge"]["model"],
                weight=params.Controlnet["softedge"]["weight"],
            )
            controlnets.append(softedge)
            params[controlnet_units] = controlnets
            params[images] = [ImageContext.image]

            result = api.img2img(**params)

            return result.image

            # optionally set username, password when --api-auth=username:password is set on webui.
            # username, password are not protected and can be derived easily if the communication channel is not encrypted.
            # you can also pass username, password to the WebUIApi constructor.
            # api.set_auth('username', 'password')

        except Exception as exc:
            raise PipelineError(f"error processing the filter {self.filter}") from exc

    def __repr__(self) -> str:
        return self.__class__.__name__
