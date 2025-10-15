from collections.abc import Sequence

import numpy as np
from PIL import Image
from PIL.Image import Image as PILImage

from .base import BaseSession


class ModnetSession(BaseSession):
    def predict(self, img: PILImage, *args, **kwargs) -> PILImage:
        """
        Predicts the output masks for the input image using the inner session.

        Parameters:
            img (PILImage): The input image.

        Returns:
            List[PILImage]: The list of output masks.
        """

        resize_to = self.get_ref_size(img.width, img.height, 512)

        ort_outs = self.inner_session.run(None, self.normalize_2(img, resize_to))
        assert isinstance(ort_outs, Sequence)
        assert isinstance(ort_outs[0], np.ndarray)

        pred: np.ndarray = ort_outs[0][:, 0, :, :]

        mask = Image.fromarray((np.squeeze(pred) * 255).astype("uint8"))

        mask = mask.resize(img.size, Image.Resampling.LANCZOS)

        return mask

    @classmethod
    def download_models(cls):
        return cls.models_included_home() / f"{cls.name()}.onnx"

    @classmethod
    def name(cls):
        return "modnet"
