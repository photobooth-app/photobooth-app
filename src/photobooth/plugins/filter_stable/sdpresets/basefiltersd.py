from dataclasses import dataclass


@dataclass
class BaseNet:
    module: str
    model: str
    enabled: bool = True
    weight: float = 0.5
    control_mode: str = "Balanced"
    processor_res: int = 512
    resize_mode: str = "Crop and Resize"


@dataclass
class BaseFilterSD:
    prompt: str = (
        ", energetic atmosphere capturing thrill of the moment, clear details, best quality, extremely detailed cg 8k wallpaper, "
        "volumetric lighting, 4k, best quality, masterpiece, ultrahigh res, group photo, sharp focus, (perfect image composition)"
    )
    negative_prompt: str = "Disfigured, cartoon, blurry"
    model: str = "dreamshaper8Pruned.hz5Q.safetensors"
    seed: int = -1
    steps: int = 20
    width: int = 768
    height: int = 512
    cfg_scale: int = 7
    n_iter: int = 1
    batch_size: int = 1
    denoising_strength: float = 0.9
    sampler_name: str = "DPM++ 2M Karras"

    # openpose: BaseNet = BaseNet(
    #     module="openpose_full",
    #     model="control_v11p_sd15_openpose [cab727d4]",
    #     enabled=True,
    #     weight=0.5,
    #     control_mode="Balanced",
    #     processor_res=512,
    #     resize_mode="Crop and Resize",
    # )

    # depth: BaseNet = BaseNet(
    #     module="depth_midas",
    #     model="control_v11f1p_sd15_depth [cfd03158]",
    #     enabled=True,
    #     weight=0.5,
    #     control_mode="Balanced",
    #     processor_res=512,
    #     resize_mode="Crop and Resize",
    # )

    # softedge: BaseNet = BaseNet(
    #     module="softedge_pidinet",
    #     model="control_v11p_sd15_softedge [a8575a2a]",
    #     enabled=True,
    #     weight=0.5,
    #     control_mode="Balanced",
    #     processor_res=512,
    #     resize_mode="Crop and Resize",
    # )
