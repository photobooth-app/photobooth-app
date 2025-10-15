import os
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

        resize_to = self.__get_scale_factor(img.width, img.height, 512)

        ort_outs = self.inner_session.run(None, self.normalize_2(img, resize_to))
        assert isinstance(ort_outs, Sequence)
        assert isinstance(ort_outs[0], np.ndarray)

        pred: np.ndarray = ort_outs[0][:, 0, :, :]

        mask = Image.fromarray((np.squeeze(pred) * 255).astype("uint8"))

        mask = mask.resize(img.size, Image.Resampling.LANCZOS)

        return mask

    @staticmethod
    def __get_scale_factor(im_w: int, im_h: int, ref_size: int) -> tuple[int, int]:
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
    def download_models(cls, *args, **kwargs):
        fname = f"{cls.name(*args, **kwargs)}.onnx"
        return os.path.join(cls.u2net_home(*args, **kwargs), fname)

    @classmethod
    def name(cls, *args, **kwargs):
        return "modnet"
