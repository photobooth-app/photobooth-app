class BaseFilterSD:
    def __init__(self) -> None:
        self.prompt = ("",)
        self.negative_prompt = ("",)
        self.images = []
        self.seed = (-1,)
        self.steps = (20,)
        self.width = (768,)
        self.height = (512,)
        self.cfg_scale = (7,)
        self.n_iter = (1,)
        self.batch_size = (1,)
        self.denoising_strength = (0.9,)
        self.sampler_name = "DPM++ 2M Karras"
        self.openpose = {
                "module": "openpose_full",
                "model": "control_v11p_sd15_openpose [cab727d4]",
                "enabled": 1,
                "weight": 0.5,
                "control_mode": "Balanced",
                "processor_res": 512,
                "resize_mode": "Crop and Resize",
            }
        
        self.depth =  {
                "module": "depth_midas",
                "model": "control_v11f1p_sd15_depth [cfd03158]",
                "enabled": 1,
                "weight": 0.5,
                "control_mode": "Balanced",
                "processor_res": 512,
                "resize_mode": "Crop and Resize",
            }
        
        self.softedge = {
                "module": "softedge_pidinet",
                "model": "control_v11p_sd15_softedge [a8575a2a]",
                "enabled": 1,
                "weight": 0.5,
                "control_mode": "Balanced",
                "processor_res": 512,
                "resize_mode": "Crop and Resize",
            }
        

        self.model = "dreamshaper8Pruned.hz5Q.safetensors"

    def getParams(self):
        return {
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "seed": self.seed,
            "steps": self.steps,
            "width": self.width,
            "height": self.height,
            "cfg_scale": self.cfg_scale,
            "batch_size": self.batch_size,
            "denoising_strength": self.denoising_strength,
            "sampler_name": self.sampler_name,
            "model": self.model,
            "depth": self.depth,
            "openpose": self.openpose,
            "softedge": self.softedge,
            "prompt": self.prompt
        }
