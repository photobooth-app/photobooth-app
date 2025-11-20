import logging
import os
import pickle
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Generic, TypeVar

logger = logging.getLogger(__name__)


T = TypeVar("T", bound="PersistableDataclass")


@dataclass
class PersistableDataclass:
    calibration_datetime: str
    img_width: int
    img_height: int

    @classmethod
    def from_file(cls: type[T], path: str | Path) -> T:
        with open(path, "rb") as handle:
            return cls(**pickle.load(handle))

    def to_file(self, path: str | bytes | os.PathLike) -> None:
        with open(path, "wb") as handle:
            pickle.dump(asdict(self), handle, protocol=pickle.HIGHEST_PROTOCOL)


class CalibrationBase(Generic[T]):
    """Base class providing save/load functionality for calibration data."""

    FILE_PREFIX = "calib"  # configurable in subclasses
    FILE_SUFFIX = ".pkl"

    def __init__(self):
        self._caldataalign: list[T] = []

    def _filename(self, cam_idx: int | str) -> str:
        """Return the filename for a given camera index."""
        return f"{self.FILE_PREFIX}_{cam_idx}{self.FILE_SUFFIX}"

    def delete_calibration_data(self, dir: Path) -> None:
        """Save all calibration data to disk."""
        if dir.exists():
            shutil.rmtree(dir)

        self.reset_calibration_data()

    def reset_calibration_data(self) -> None:
        self._caldataalign = []

    def save_calibration_data(self, dir: Path) -> None:
        """Save all calibration data to disk."""

        # ensure dir exists
        dir.mkdir(parents=True, exist_ok=True)

        for cam_idx, calib_data in enumerate(self._caldataalign):
            calib_data.to_file(dir / self._filename(cam_idx))

        logger.info("Saved calibration data for cameras: %s", ", ".join(map(str, range(len(self._caldataalign)))))

    def _load_calibration_data(self, dir: Path, caldata_cls: type[T]) -> None:
        """Load all calibration data from disk, to be invoked from inheriting class providing the correct dataclass"""
        pattern = self._filename("*")
        files = sorted(dir.glob(pattern))

        self._caldataalign = [caldata_cls.from_file(f) for f in files]

        if not self._caldataalign:
            raise ValueError(f"No calibration data found in {dir}")

        logger.info("Loaded calibration data for cameras: %s", ", ".join(map(str, range(len(self._caldataalign)))))

    def is_calibration_data_valid(self, expected_device_ids: tuple[int, ...]) -> bool:
        return bool(self._caldataalign) and set(expected_device_ids).issubset(range(len(self._caldataalign)))
