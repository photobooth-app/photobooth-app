from pathlib import Path
from typing import Any


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
