from collections.abc import Sequence
from pathlib import Path

import numpy as np
from PIL import Image
from PIL.Image import Image as PILImage

from .base import BaseSession


class U2netSession(BaseSession):
    def predict(self, img: PILImage, *args, **kwargs) -> PILImage:
        """
        Predicts the output masks for the input image using the inner session.

        Parameters:
            img (PILImage): The input image.

        Returns:
            List[PILImage]: The list of output masks.
        """
        ort_outs = self.inner_session.run(None, self.normalize_imagenet(img, (0.485, 0.456, 0.406), (0.229, 0.224, 0.225), (320, 320)))
        assert isinstance(ort_outs, Sequence)
        assert isinstance(ort_outs[0], np.ndarray)

        pred: np.ndarray = ort_outs[0][:, 0, :, :]

        ma = np.max(pred)
        mi = np.min(pred)

        pred = (pred - mi) / (ma - mi)
        pred = np.squeeze(pred)

        mask = Image.fromarray((pred.clip(0, 1) * 255).astype("uint8"))
        mask = mask.resize(img.size, Image.Resampling.LANCZOS)

        return mask

    @classmethod
    def download_models(cls):
        fname = f"{cls.name()}.onnx"
        fpath = Path(cls.models_download_home(), fname)

        # url = "https://github.com/photobooth-app/photobooth-app/releases/download/untagged-dd4eac6e113053f0f7fa/u2net.onnx"
        url = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx"
        hash_valid = "60024c5c889badc19c04ad937298a77b"

        cls.retrieve_model(fpath, hash_valid, url)

        return str(fpath.absolute())

    @classmethod
    def name(cls):
        return "u2net"
