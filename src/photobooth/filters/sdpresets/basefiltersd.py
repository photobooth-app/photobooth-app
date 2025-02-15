class BaseFilterSD:
    def __init__(self) -> None:
        self.prompt = ("",)
        self.negative_prompt = ("",)
        self.init_images = ([],)
        self.seed = (-1,)
        self.steps = (20,)
        self.width = (768,)
        self.height = (512,)
        self.cfg_scale = (7,)
        self.n_iter = (1,)
        self.batch_size = (1,)
        self.denoising_strength = (0.9,)
        self.sampler_name = "DPM++ 2M Karras"
        self.Controlnet["openpose"] = (
            {
                "module": "openpose_full",
                "model": "control_v11p_sd15_openpose",
                "enabled": 1,
                "weight": 0.5,
                "control_mode": "Balanced",
                "processor_res": 512,
                "resize_mode": "Crop and Resize",
            },
        )
        self.Controlnet["depth"] = (
            {
                "module": "depth_midas",
                "model": "control_v11f1p_sd15_depth",
                "enabled": 1,
                "weight": 0.5,
                "control_mode": "Balanced",
                "processor_res": 512,
                "resize_mode": "Crop and Resize",
            },
        )
        self.Controlnet["softedge"] = (
            {
                "module": "softedge_pidinet",
                "model": "control_v11p_sd15_softedge",
                "enabled": 1,
                "weight": 0.5,
                "control_mode": "Balanced",
                "processor_res": 512,
                "resize_mode": "Crop and Resize",
            },
        )

        self.model = "dreamshaper8Pruned.hz5Q.safetensors"
