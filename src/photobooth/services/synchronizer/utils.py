import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_remote_filepath(local_filepath: Path, local_root_dir: Path = Path("./media/")) -> Path:
    try:
        remote_path = local_filepath.relative_to(local_root_dir)
    except ValueError as exc:
        raise ValueError(f"file {local_filepath} needs to be below root dir {local_root_dir}.") from exc

    return remote_path
