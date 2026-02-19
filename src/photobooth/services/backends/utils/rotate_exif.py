import io
from pathlib import Path
from typing import overload

import piexif

from photobooth.services.config.groups.cameras import Orientation


@overload
def set_exif_orientation(jpeg_image: Path, orientation_choice) -> Path: ...
@overload
def set_exif_orientation(jpeg_image: bytes, orientation_choice) -> bytes: ...


def set_exif_orientation(jpeg_image: Path | bytes, orientation_choice: Orientation) -> Path | bytes:
    """inserts updated orientation flag in given filepath.
    ref https://sirv.com/help/articles/rotate-photos-to-be-upright/

    Args:
        jpeg_image (Path|bytes): jpeg to modify
        orientation_choice (Literal): Orientierung (1=0°, 3=180°, 5=90°, 7=270°)
    """

    def _get_updated_exif_bytes(maybe_image, orientation_choice: Orientation):
        assert isinstance(orientation_choice, str)

        orientation = int(orientation_choice[0])
        if 1 < orientation > 8:
            raise ValueError(f"invalid orientation choice {orientation_choice} results in invalid value: {orientation}.")

        exif_dict = piexif.load(maybe_image)
        exif_dict["0th"][piexif.ImageIFD.Orientation] = orientation

        return piexif.dump(exif_dict)

    if isinstance(jpeg_image, Path):
        # File case: update in place
        piexif.insert(_get_updated_exif_bytes(str(jpeg_image), orientation_choice), str(jpeg_image))
        return jpeg_image
    elif isinstance(jpeg_image, (bytes, bytearray)):
        # Bytes case: return new data
        output = io.BytesIO()
        piexif.insert(_get_updated_exif_bytes(jpeg_image, orientation_choice), jpeg_image, output)
        return output.getvalue()
    # else: ...           #not going to happen as per type
