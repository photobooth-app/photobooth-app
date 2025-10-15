from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image
from PIL.Image import Image as PILImage


class BaseSession:
    """This is a base class for managing a session with a machine learning model."""

    def __init__(self, model_name: str, sess_opts: ort.SessionOptions, *args, **kwargs):
        """Initialize an instance of the BaseSession class."""
        self.model_name = model_name

        if "providers" in kwargs and isinstance(kwargs["providers"], list):
            providers = kwargs.pop("providers")
        else:
            device_type = ort.get_device()
            if device_type == "GPU" and "CUDAExecutionProvider" in ort.get_available_providers():
                providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            elif device_type[0:3] == "GPU" and "ROCMExecutionProvider" in ort.get_available_providers():
                providers = ["ROCMExecutionProvider", "CPUExecutionProvider"]
            else:
                providers = ["CPUExecutionProvider"]

        self.inner_session = ort.InferenceSession(
            str(self.__class__.download_models(*args, **kwargs)),
            sess_options=sess_opts,
            providers=providers,
        )

    def normalize_imagenet(
        self, img: PILImage, mean: tuple[float, float, float], std: tuple[float, float, float], size: tuple[int, int], *args, **kwargs
    ) -> dict[str, np.ndarray]:
        im = img.convert("RGB").resize(size, Image.Resampling.LANCZOS)

        im_ary = np.array(im)
        im_ary = im_ary / max(np.max(im_ary), 1e-6)

        tmpImg = np.zeros((im_ary.shape[0], im_ary.shape[1], 3))
        tmpImg[:, :, 0] = (im_ary[:, :, 0] - mean[0]) / std[0]
        tmpImg[:, :, 1] = (im_ary[:, :, 1] - mean[1]) / std[1]
        tmpImg[:, :, 2] = (im_ary[:, :, 2] - mean[2]) / std[2]

        tmpImg = tmpImg.transpose((2, 0, 1))

        return {self.inner_session.get_inputs()[0].name: np.expand_dims(tmpImg, 0).astype(np.float32)}

    def normalize_2(self, img: PILImage, size: tuple[int, int], *args, **kwargs) -> dict[str, np.ndarray]:
        im = img.convert("RGB").resize(size, Image.Resampling.LANCZOS)

        # Convert to numpy array (H height, W width, C channels), dtype float32
        im_ary = np.array(im).astype(np.float32)
        im_ary = (im_ary - 127.5) / 127.5

        # Change to (C, H, W) as ONNX expects channels-first
        im_ary = im_ary.transpose((2, 0, 1))

        return {self.inner_session.get_inputs()[0].name: np.expand_dims(im_ary, 0).astype(np.float32)}  # add batch dimension (1,C,H,W)

    def predict(self, img: PILImage, *args, **kwargs) -> PILImage:
        raise NotImplementedError

    @staticmethod
    def get_ref_size(im_w: int, im_h: int, ref_size: int) -> tuple[int, int]:
        im_rw, im_rh = im_w, im_h

        if max(im_h, im_w) < ref_size or min(im_h, im_w) > ref_size:
            if im_w >= im_h:
                im_rh = ref_size
                im_rw = int(im_w / im_h * ref_size)
            else:  # im_w < im_h
                im_rw = ref_size
                im_rh = int(im_h / im_w * ref_size)

        im_rw = im_rw - im_rw % 32
        im_rh = im_rh - im_rh % 32

        return (im_rw, im_rh)

    @classmethod
    def u2net_home(cls, *args, **kwargs):
        return Path(__file__).parent.parent / "models"
        # return os.path.expanduser(os.getenv("U2NET_HOME", os.path.join(os.getenv("XDG_DATA_HOME", "~"), ".u2net")))

    @classmethod
    def download_models(cls, *args, **kwargs) -> str:
        raise NotImplementedError

    @classmethod
    def name(cls, *args, **kwargs) -> str:
        raise NotImplementedError
