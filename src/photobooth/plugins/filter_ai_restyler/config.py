from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FilePath,
    HttpUrl,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    SecretStr,
    SerializationInfo,
    field_serializer,
    field_validator,
)
from pydantic_settings import SettingsConfigDict

from ... import CONFIG_PATH
from ...services.config.baseconfig import BaseConfig
from ...services.config.serializer import contextual_serializer_password


class ProviderParameter(BaseModel):
    model_config = ConfigDict(title="Parameter")

    key: str = Field(description="Name of the parameter sent to the provider.")
    value: str = Field(description="Value of the parameter. Numbers, booleans and JSON objects are sent with their JSON type.")


class AiStyle(BaseModel):
    model_config = ConfigDict(title="AI Style")

    id: str = Field(
        pattern=r"^[a-z0-9_-]+$",
        description="Unique identifier of the style (lowercase letters, numbers, '-' and '_' only). Used to reference the filter in actions.",
    )
    name: str = Field(description="Display name of the style.")
    prompt: str = Field(description="Description of the style. It is inserted into the prompt template at {style}.")
    negative_prompt: str = Field(
        default="", description="Optional negative prompt. Only used by ComfyUI workflows with a {{negative_prompt}} placeholder."
    )
    userselectable: bool = Field(default=True, description="Users can choose this style in the gallery.")
    preview_image: FilePath | None = Field(
        default=None,
        description="Optional sample image shown as the preview in the filter selection. The image is center-cropped to the photo's aspect ratio without resizing. If empty, the preview shipped with the plugin for this style id is used. No AI request is made for previews.",
        json_schema_extra={"list_api": "/api/admin/enumerate/userfiles"},
    )


class _ApiKeyProviderConfig(BaseModel):
    api_key: SecretStr = Field(default=SecretStr(""), description="API key of the provider.")
    timeout: PositiveFloat = Field(default=30.0, description="Maximum time in seconds to wait for a result.")
    extra_params: list[ProviderParameter] = Field(default=[], description="Additional parameters sent to the model.")

    @field_serializer("api_key")
    def contextual_serializer(self, value, info: SerializationInfo):
        return contextual_serializer_password(value, info)


class FalProviderConfig(_ApiKeyProviderConfig):
    model_config = ConfigDict(title="fal.ai")
    provider_type: Literal["fal"] = "fal"

    base_url: HttpUrl = Field(default=HttpUrl("https://fal.run"), description="fal.ai synchronous API endpoint.")
    model_id: str = Field(
        default="fal-ai/flux-pro/kontext", description="fal.ai model id of an image-edit model, for example 'fal-ai/flux-pro/kontext'."
    )
    image_param_name: str = Field(default="image_url", description="Name of the input image parameter of the model.")


class ReplicateProviderConfig(_ApiKeyProviderConfig):
    model_config = ConfigDict(title="Replicate")
    provider_type: Literal["replicate"] = "replicate"

    base_url: HttpUrl = Field(default=HttpUrl("https://api.replicate.com/v1"), description="Replicate API endpoint.")
    model_id: str = Field(
        default="black-forest-labs/flux-kontext-pro",
        description="Replicate model as 'owner/model' or a specific version as 'owner/model:version'.",
    )
    image_param_name: str = Field(default="input_image", description="Name of the input image parameter of the model.")
    extra_params: list[ProviderParameter] = Field(
        default=[
            ProviderParameter(key="aspect_ratio", value="match_input_image"),
            ProviderParameter(key="output_format", value="jpg"),
        ],
        description="Additional parameters sent to the model.",
    )


class ComfyUIProviderConfig(BaseModel):
    model_config = ConfigDict(title="ComfyUI (local)")
    provider_type: Literal["comfyui"] = "comfyui"

    base_url: HttpUrl = Field(default=HttpUrl("http://127.0.0.1:8188"), description="URL of the ComfyUI server.")
    api_key: SecretStr = Field(default=SecretStr(""), description="Optional bearer token if ComfyUI is behind an authenticating proxy.")
    workflow_file: FilePath | None = Field(
        default=None,
        description="Workflow exported from ComfyUI in API format. Use the placeholders {{image}}, {{prompt}}, {{negative_prompt}} and {{seed}}.",
        json_schema_extra={"list_api": "/api/admin/enumerate/userfiles"},
    )
    timeout: PositiveFloat = Field(default=60.0, description="Maximum time in seconds to wait for a result.")

    @field_serializer("api_key")
    def contextual_serializer(self, value, info: SerializationInfo):
        return contextual_serializer_password(value, info)


ProviderConfig = ReplicateProviderConfig | FalProviderConfig | ComfyUIProviderConfig


DEFAULT_STYLES = [
    AiStyle(
        id="vintage-1920s",
        name="1920s",
        prompt=(
            "a black-and-white 1920s photograph with period-appropriate clothing and surroundings, "
            "while preserving each person's face, hairstyle, facial hair, age and gender presentation"
        ),
    ),
    AiStyle(id="pixar-3d", name="3D Animation", prompt="a 3D animated movie character render with soft lighting"),
    AiStyle(
        id="anime",
        name="Anime",
        prompt="a Japanese anime illustration with clean line art, large expressive eyes, flat cel shading and vibrant colors",
    ),
    AiStyle(id="astronaut", name="Astronaut", prompt="a realistic photo with astronaut spacesuits and faces clearly visible"),
    AiStyle(id="lego", name="Brick Figures", prompt="toy brick minifigures built from plastic bricks"),
    AiStyle(id="cartoon", name="Cartoon", prompt="a colorful 2D cartoon illustration with bold outlines"),
    AiStyle(id="clay", name="Clay Figure", prompt="a stop-motion clay animation with handcrafted figures and textured surfaces"),
    AiStyle(id="comic", name="Comic Book", prompt="a comic book panel with ink lines and halftone shading"),
    AiStyle(id="cyberpunk", name="Cyberpunk", prompt="a cyberpunk scene with neon lights and futuristic clothing"),
    AiStyle(id="impasto", name="Impasto Painting", prompt="an oil painting with thick, textured brushstrokes"),
    AiStyle(
        id="kids",
        name="Kids' Illustration",
        prompt="a whimsical children's storybook illustration with soft pastels and hand-drawn details, keeping people their original ages",
    ),
    AiStyle(
        id="marble",
        name="Marble Sculpture",
        prompt="a white Carrara marble sculpture with finely chiseled details, natural stone veins and soft museum lighting",
    ),
    AiStyle(id="medieval", name="Medieval", prompt="a medieval painting, people dressed in medieval clothing in a castle setting"),
    AiStyle(
        id="neotokyo",
        name="Neo Tokyo",
        prompt="a 1990s hand-drawn cyberpunk anime scene with cel shading and neon-lit Japanese city details",
    ),
    AiStyle(
        id="pencil-sketch",
        name="Pencil Sketch",
        prompt="a detailed graphite pencil sketch with fine cross-hatching and soft shading on white paper",
    ),
    AiStyle(id="pop-art", name="Pop Art", prompt="a pop art print with bright flat colors and ben-day dots"),
    AiStyle(id="renaissance", name="Renaissance", prompt="a renaissance oil painting with dramatic chiaroscuro lighting"),
    AiStyle(
        id="retro",
        name="Retro Illustration",
        prompt="a mid-century retro illustration with flat pastel colors, geometric shapes and vintage print texture",
    ),
    AiStyle(
        id="scifi",
        name="Sci-Fi",
        prompt="a bright science-fiction film scene with clean futuristic architecture, metallic details and cool lighting",
    ),
    AiStyle(
        id="superhero",
        name="Superhero",
        prompt="a cinematic superhero scene with colorful heroic costumes and capes, keeping each person's face uncovered and recognizable",
    ),
    AiStyle(id="vaporwave", name="Vaporwave", prompt="a vaporwave illustration with pastel pink and turquoise colors and retro digital textures"),
    AiStyle(id="watercolor", name="Watercolor", prompt="a soft watercolor painting on textured paper"),
]


class Common(BaseModel):
    enabled: bool = Field(
        default=False,
        description="Enable AI restyling. Images are sent to the selected provider. If you use a cloud provider, each processed image is billed "
        "by the provider and personal data leaves the device, so inform your guests.",
    )
    prompt_template: str = Field(
        default=(
            "Convert this photo into {style}. Keep every person in the exact same position, scale and pose, with identical camera angle, "
            "framing and perspective. Preserve each person's facial features, face shape, eyes, nose, jawline, hairstyle, facial hair, skin tone, "
            "age and gender presentation so they stay clearly recognizable. Keep the number of people and their expressions unchanged. "
            "Only change the artistic rendering, clothing and background to match the style."
        ),
        description="Prompt sent to the model. {style} is replaced by the prompt of the selected style.",
    )
    max_input_size: PositiveInt = Field(
        default=1024,
        description="Images are downscaled to this length of the longest side before upload. The result is scaled back to the original size.",
    )
    max_concurrent_requests: PositiveInt = Field(default=2, description="Maximum number of requests processed at the same time.")
    cache_max_entries: NonNegativeInt = Field(
        default=200,
        description="Results are cached so reprocessing does not trigger a new paid request. Set to 0 to disable the cache.",
    )

    add_userselectable_filter: bool = Field(
        default=True, description="Add the styles to the filters the user can choose from. Otherwise you can only set them in the actions."
    )


class FilterAiRestylerConfig(BaseConfig):
    model_config = SettingsConfigDict(
        title="Filter Stage AI Restyler Plugin Config",
        json_file=f"{CONFIG_PATH}plugin_filter_ai_restyler.json",
        env_prefix="filter-ai-restyler-",
    )

    common: Common = Common()
    provider: ProviderConfig = Field(
        default=ReplicateProviderConfig(),
        discriminator="provider_type",
        description="Provider used to restyle images.",
    )

    styles: list[AiStyle] = Field(
        default=DEFAULT_STYLES,
        description="Available styles. Add your own styles here. Restart the app after adding, renaming or removing styles.",
    )

    @field_validator("styles")
    @classmethod
    def unique_style_ids(cls, styles: list[AiStyle]) -> list[AiStyle]:
        ids = [style.id for style in styles]
        duplicates = sorted({_id for _id in ids if ids.count(_id) > 1})
        if duplicates:
            raise ValueError(f"style ids must be unique, duplicates: {duplicates}")
        return styles

    def get_style(self, style_id: str) -> AiStyle:
        for style in self.styles:
            if style.id == style_id:
                return style

        raise ValueError(f"AI style '{style_id}' is not configured")
