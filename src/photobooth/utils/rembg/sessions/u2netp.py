from collections.abc import Sequence

import numpy as np
from PIL import Image
from PIL.Image import Image as PILImage

from .base import BaseSession


class U2netpSession(BaseSession):
    def predict(self, img: PILImage, *args, **kwargs) -> PILImage:
        """
        Predicts the mask for the given image using the U2netp model.

        Parameters:
            img (PILImage): The input image.

        Returns:
            List[PILImage]: The predicted mask.
        """
        ort_outs = self.inner_session.run(None, self.normalize_imagenet(img, (0.485, 0.456, 0.406), (0.229, 0.224, 0.225), (320, 320)))
        assert isinstance(ort_outs, Sequence)
        assert isinstance(ort_outs[0], np.ndarray)

        pred: np.ndarray = ort_outs[0][:, 0, :, :]

        ma = np.max(pred)
        mi = np.min(pred)

        pred = (pred - mi) / (ma - mi)
        pred = np.squeeze(pred)

        mask = Image.fromarray((pred * 255).astype("uint8"))
        mask = mask.resize(img.size, Image.Resampling.LANCZOS)

        return mask

    @classmethod
    def download_models(cls):
        return cls.models_included_home() / f"{cls.name()}.onnx"

    @classmethod
    def name(cls):
        return "u2netp"
