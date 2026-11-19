import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def ensure_remote_base_path(rclone, remote) -> None:
    """Create bucket and subdir on the remote if missing (no-op if they exist).

    Only done if a bucket is configured: without bucket the base path must pre-exist, which
    protects against writing into the mountpoint dir of a usb drive that is not attached.
    Raises an exception if the remote is unreachable or the credentials do not allow creation.
    """
    if not remote.bucket:
        return

    # rclone's operations/mkdir (same as `rclone mkdir remote:bucket/subdir`) creates the bucket if missing
    # and is a no-op if it exists; dirs below are implicit/created as needed.
    # RcloneApi has no mkdir wrapper (yet), so the rc endpoint is called directly.
    rclone._post("operations/mkdir", {"fs": remote.name, "remote": remote.base_path})


def get_corresponding_remote_file(local_filepath: Path, local_root_dir: Path = Path("./media/")) -> Path:
    try:
        remote_path = local_root_dir / local_filepath.relative_to(local_root_dir)
    except ValueError as exc:
        raise ValueError(f"file {local_filepath} needs to be below root dir {local_root_dir}.") from exc

    return remote_path
