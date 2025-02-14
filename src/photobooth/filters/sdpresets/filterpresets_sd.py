import photobooth.filters.sdpresets.basefiltersd as basefiltersd


class ClayFilterSD(basefiltersd):
    def __init__(self) -> None:
        self.name = "clay"
        self.icon = "clay.png"
        self.label = "Clay Figure"
        self.model = "dreamshaper8Pruned.hz5Q.safetensors"
        self.Controlnet["depth"]["weight"] = 0.7
        self.Controlnet["openpose"]["weight"] = 0.8
        self.Controlnet["softegde"]["weight"] = 0.4
        self.prompt = "clazy style, claymation, stopmotion, small clay figure, vibrant colors, fantastic plastic <lora:ClayAnimationRedmond15-ClayAnimation-Clay:0.7>"
        self.enabled = 1

    def getParams(self):
        return {
            "name": self.name,
            "icon": self.icon,
            "label": self.label,
            "model": self.model,
            "depth": self.depth,
            "openpose": self.openpose,
            "softegde": self.softegde,
            "prompt": self.prompt,
            "enabled": self.enabled,
        }


class GotchaFilterSD(basefiltersd):
    def __init__(self) -> None:
        self.name = "gotcha"
        self.icon = "gotcha.png"
        self.label = "Gotcha!"
        self.model = "dreamshaper8Pruned.hz5Q.safetensors"
        self.Controlnet["depth"]["weight"] = 0.5
        self.Controlnet["openpose"]["weight"] = 0.5
        self.Controlnet["softegde"]["weight"] = 0.4
        self.prompt = (
            "stylized cartoon, illustration, portrait of persons and an animal, looking sideways, forest in the background <lora:gotchaV001.Yu4Z:0.4>"
        )
        self.enabled = 1

    def getParams(self):
        return {
            "name": self.name,
            "icon": self.icon,
            "label": self.label,
            "model": self.model,
            "depth": self.depth,
            "openpose": self.openpose,
            "softegde": self.softegde,
            "prompt": self.prompt,
            "enabled": self.enabled,
        }


class ImpastoFilterSD(basefiltersd):
    def __init__(self) -> None:
        self.name = "impasto"
        self.icon = "impasto.png"
        self.label = "Impasto Painting"
        self.model = "dreamshaper8Pruned.hz5Q.safetensors"
        self.Controlnet["depth"]["weight"] = 0.6
        self.Controlnet["openpose"]["weight"] = 0.6
        self.Controlnet["softegde"]["weight"] = 0.3
        self.prompt = "((impasto)), intricate oil painting, thick textured paint, artistic, old holland classic colors, portrait"
        self.enabled = 1

    def getParams(self):
        return {
            "name": self.name,
            "icon": self.icon,
            "label": self.label,
            "model": self.model,
            "depth": self.depth,
            "openpose": self.openpose,
            "softegde": self.softegde,
            "prompt": self.prompt,
            "enabled": self.enabled,
        }


class KidsFilterSD(basefiltersd):
    def __init__(self) -> None:
        self.name = "kids"
        self.icon = "kids.png"
        self.label = "Kids Illustration"
        self.model = "dreamshaper8Pruned.hz5Q.safetensors"
        self.Controlnet["depth"]["weight"] = 0.7
        self.Controlnet["openpose"]["weight"] = 0.9
        self.Controlnet["softegde"]["weight"] = 0.4
        self.prompt = (
            "kids illustration, children's cartoon, happy persons, looking at the camera, kitchen in the background <lora:coolkidsMERGEV25.Qqci:1>"
        )
        self.enabled = 1

    def getParams(self):
        return {
            "name": self.name,
            "icon": self.icon,
            "label": self.label,
            "model": self.model,
            "depth": self.depth,
            "openpose": self.openpose,
            "softegde": self.softegde,
            "prompt": self.prompt,
            "enabled": self.enabled,
        }


class MarbleFilterSD(basefiltersd):
    def __init__(self) -> None:
        self.name = "marble"
        self.icon = "marble.png"
        self.label = "marble sculpture in a museum"
        self.model = "dreamshaper8Pruned.hz5Q.safetensors"
        self.Controlnet["depth"]["weight"] = 0.5
        self.Controlnet["openpose"]["weight"] = 1.0
        self.Controlnet["softegde"]["weight"] = 0.4
        self.prompt = "marble sculpture in a museum, bust of persons, greek hills, art gallery in the background, realistic photo"
        self.enabled = 1

    def getParams(self):
        return {
            "name": self.name,
            "icon": self.icon,
            "label": self.label,
            "model": self.model,
            "depth": self.depth,
            "openpose": self.openpose,
            "softegde": self.softegde,
            "prompt": self.prompt,
            "enabled": self.enabled,
        }


class PencilFilterSD(basefiltersd):
    def __init__(self) -> None:
        self.name = "pencil"
        self.icon = "pencil.png"
        self.label = "Pencil Sketch"
        self.model = "absolutereality181.n8IR.safetensors"
        self.Controlnet["depth"]["weight"] = 0.8
        self.Controlnet["openpose"]["weight"] = 0.8
        self.Controlnet["softegde"]["weight"] = 0.3
        self.prompt = "very rough pencil sketch, persons, black-and white, hand-drawn, scribble"
        self.enabled = 1

    def getParams(self):
        return {
            "name": self.name,
            "icon": self.icon,
            "label": self.label,
            "model": self.model,
            "depth": self.depth,
            "openpose": self.openpose,
            "softegde": self.softegde,
            "prompt": self.prompt,
            "enabled": self.enabled,
        }


class RetroFilterSD(basefiltersd):
    def __init__(self) -> None:
        self.name = "retro"
        self.icon = "retro.png"
        self.label = "Retro Stylized"
        self.model = "dreamshaper8Pruned.hz5Q.safetensors"
        self.Controlnet["depth"]["weight"] = 0.8
        self.Controlnet["openpose"]["weight"] = 0.6
        self.Controlnet["softegde"]["weight"] = 0.4
        self.prompt = "stylized retro illustration, low palette, pastel colors, sharp lines, band album cover, persons"
        self.enabled = 1

    def getParams(self):
        return {
            "name": self.name,
            "icon": self.icon,
            "label": self.label,
            "model": self.model,
            "depth": self.depth,
            "openpose": self.openpose,
            "softegde": self.softegde,
            "prompt": self.prompt,
            "enabled": self.enabled,
        }


class ScifiFilterSD(basefiltersd):
    def __init__(self) -> None:
        self.name = "scifi"
        self.icon = "scifi.png"
        self.label = "Sci-Fi"
        self.model = "dreamshaper8Pruned.hz5Q.safetensors"
        self.Controlnet["depth"]["weight"] = 1.0
        self.Controlnet["openpose"]["weight"] = 0.8
        self.Controlnet["softegde"]["weight"] = 0.6
        self.prompt = "futuristic sci-fi movie, persons, neon lights illumination, distant night city in the background"
        self.enabled = 1

    def getParams(self):
        return {
            "name": self.name,
            "icon": self.icon,
            "label": self.label,
            "model": self.model,
            "depth": self.depth,
            "openpose": self.openpose,
            "softegde": self.softegde,
            "prompt": self.prompt,
            "enabled": self.enabled,
        }


class ComicFilterSD(basefiltersd):
    def __init__(self) -> None:
        self.name = "comic"
        self.icon = "western.png"
        self.label = "Western Comic"
        self.model = "westernanidiffusion.EpVW.safetensors"
        self.Controlnet["depth"]["weight"] = 0.7
        self.Controlnet["openpose"]["weight"] = 0.8
        self.Controlnet["softegde"]["weight"] = 0.4
        self.prompt = "western comic, portrait, superman, looking to the side, metropolis in the background"
        self.enabled = 1

    def getParams(self):
        return {
            "name": self.name,
            "icon": self.icon,
            "label": self.label,
            "model": self.model,
            "depth": self.depth,
            "openpose": self.openpose,
            "softegde": self.softegde,
            "prompt": self.prompt,
            "enabled": self.enabled,
        }


class AnimeFilterSD(basefiltersd):
    def __init__(self) -> None:
        self.name = "anime"
        self.icon = "anime.png"
        self.label = "Anime"
        self.model = "animepasteldreamSoft.lTTK.safetensors"
        self.Controlnet["depth"]["weight"] = 0.9
        self.Controlnet["openpose"]["weight"] = 1.0
        self.Controlnet["softegde"]["weight"] = 0.6
        self.prompt = "anime illustration, movie still, person, smiling and happy, looking sideways, bright sun, summer, small town in the background"
        self.enabled = 1

    def getParams(self):
        return {
            "name": self.name,
            "icon": self.icon,
            "label": self.label,
            "model": self.model,
            "depth": self.depth,
            "openpose": self.openpose,
            "softegde": self.softegde,
            "prompt": self.prompt,
            "enabled": self.enabled,
        }


class MedievalFilterSD(basefiltersd):
    def __init__(self) -> None:
        self.name = "medieval"
        self.icon = "medieval.png"
        self.label = "Medieval Painting"
        self.model = "dreamshaper8Pruned.hz5Q.safetensors"
        self.Controlnet["depth"]["weight"] = 0.4
        self.Controlnet["openpose"]["weight"] = 0.6
        self.Controlnet["softegde"]["weight"] = 0.2
        self.prompt = "bad medieval painting, framed, textured paint, scene with a person, stabbing king"
        self.enabled = 1

    def getParams(self):
        return {
            "name": self.name,
            "icon": self.icon,
            "label": self.label,
            "model": self.model,
            "depth": self.depth,
            "openpose": self.openpose,
            "softegde": self.softegde,
            "prompt": self.prompt,
            "enabled": self.enabled,
        }


class AstronautFilterSD(basefiltersd):
    def __init__(self) -> None:
        self.name = "astronaut"
        self.icon = "astronaut.png"
        self.label = "Astronaut"
        self.model = "dreamshaper8Pruned.hz5Q.safetensors"
        self.Controlnet["depth"]["weight"] = 0.6
        self.Controlnet["openpose"]["weight"] = 0.9
        self.Controlnet["softegde"]["weight"] = 0.4
        self.prompt = (
            "portrait of a NASA astronaut in spacesuit before rocket launch, space photography in the background, realistic photo, shot on DSLR"
        )
        self.enabled = 1

    def getParams(self):
        return {
            "name": self.name,
            "icon": self.icon,
            "label": self.label,
            "model": self.model,
            "depth": self.depth,
            "openpose": self.openpose,
            "softegde": self.softegde,
            "prompt": self.prompt,
            "enabled": self.enabled,
        }


class CaricatureFilterSD(basefiltersd):
    def __init__(self) -> None:
        self.name = "caricature"
        self.icon = "caricature.png"
        self.label = "Heavily caricaturized painting"
        self.model = "caricaturizer_pcrc_style.uwgn1lmj.q5b.ckpt"
        self.Controlnet["depth"]["weight"] = 0.6
        self.Controlnet["openpose"]["weight"] = 0.4
        self.Controlnet["softegde"]["weight"] = 0.1
        self.prompt = "caricature, hand-drawn illustration, portrait of a person, looking sideways"
        self.enabled = 1

    def getParams(self):
        return {
            "name": self.name,
            "icon": self.icon,
            "label": self.label,
            "model": self.model,
            "depth": self.depth,
            "openpose": self.openpose,
            "softegde": self.softegde,
            "prompt": self.prompt,
            "enabled": self.enabled,
        }


class neotokyoFilterSD(basefiltersd):
    def __init__(self) -> None:
        self.name = "neotokyo"
        self.icon = "neotokyo.png"
        self.label = "NEOTOKIO"
        self.model = "dreamshaper8Pruned.hz5Q.safetensors"
        self.Controlnet["depth"]["weight"] = 1.0
        self.Controlnet["openpose"]["weight"] = 0.8
        self.Controlnet["softegde"]["weight"] = 0.4
        self.prompt = "neotokio, 90s anime, persons, looking at the camera, portrait, evening, narrow alley in the background, bright neon signs <lora:NEOTOKIO_V0.01:0.7>"
        self.enabled = 1

    def getParams(self):
        return {
            "name": self.name,
            "icon": self.icon,
            "label": self.label,
            "model": self.model,
            "depth": self.depth,
            "openpose": self.openpose,
            "softegde": self.softegde,
            "prompt": self.prompt,
            "enabled": self.enabled,
        }


class VaporwaveFilterSD(basefiltersd):
    def __init__(self) -> None:
        self.name = "vaporwave"
        self.icon = "vaporwave.png"
        self.label = "NEOTOKIO"
        self.model = "dreamshaper8Pruned.hz5Q.safetensors"
        self.Controlnet["depth"]["weight"] = 1.0
        self.Controlnet["openpose"]["weight"] = 0.8
        self.Controlnet["softegde"]["weight"] = 0.6
        self.prompt = "vaporwave, illustration, vibrant colors, neon background, flying hair, persons"
        self.enabled = 1

    def getParams(self):
        return {
            "name": self.name,
            "icon": self.icon,
            "label": self.label,
            "model": self.model,
            "depth": self.depth,
            "openpose": self.openpose,
            "softegde": self.softegde,
            "prompt": self.prompt,
            "enabled": self.enabled,
        }


class WatercolorFilterSD(basefiltersd):
    def __init__(self) -> None:
        self.name = "watercolor"
        self.icon = "watercolor.png"
        self.label = "Watercolor"
        self.model = "dreamshaper8Pruned.hz5Q.safetensors"
        self.Controlnet["depth"]["weight"] = 0.8
        self.Controlnet["openpose"]["weight"] = 0.9
        self.Controlnet["softegde"]["weight"] = 0.4
        self.prompt = "watercolor painting, hand-drawn illustration, portrait of a person, looking sideways, clear white paper background <lora:watercolorv1.7lox:1>"
        self.enabled = 1

    def getParams(self):
        return {
            "name": self.name,
            "icon": self.icon,
            "label": self.label,
            "model": self.model,
            "depth": self.depth,
            "openpose": self.openpose,
            "softegde": self.softegde,
            "prompt": self.prompt,
            "enabled": self.enabled,
        }
