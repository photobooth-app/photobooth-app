import logging
from pathlib import Path
from typing import Any

from pydantic import SerializationInfo

logger = logging.getLogger(__name__)


def contextual_serializer_password(value: Any, info: SerializationInfo):
    if info.context:
        if info.context.get("secrets_is_allowed", False):
            return value.get_secret_value()

    return "************"


def ensure_demoassets(value: Any) -> Any:
    """
    added in v6 after FilePath checking introduced and demoassets are symlinked to userdata
    it tries to find the file in demoassets and if so returns an updated value.
    """
    if not value or value == "":
        return None

    # have it always relative!
    value = str(value).strip("/\\")

    path = Path(value)
    if not path.exists():
        list_path = list(path.parts)
        list_path.insert(1, "demoassets")
        demoassets_path = Path().joinpath(*list_path)

        if demoassets_path.exists():
            return str(demoassets_path)
        else:
            raise ValueError(f"{value} could not be validated and automatic migration failed")

    else:
        return value


def ensure_no_webcamcv2(value: Any) -> Any:
    """
    added in v7 after removing webcam cv2 backend in favor of pyav
    """
    if not value or value == "":
        return None

    if value == "WebcamCv2":
        logger.warning(
            "🤔 Updated WebcamCv2 backend to WebcamPyav! Cv2 backend is not available any more. "
            "Please check release document for v7 for additional information."
        )
        return "WebcamPyav"

    else:
        return value
