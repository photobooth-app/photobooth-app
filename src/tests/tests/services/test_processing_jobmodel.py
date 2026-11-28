import logging
import time
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from photobooth.services.acquisition import AcquisitionService
from photobooth.services.config.groups.actions import SingleImageConfigurationSet, SingleImageJobControl, SingleImageProcessing, Trigger
from photobooth.services.processor import base as processor_base
from photobooth.services.processor.image import JobModelImage
from photobooth.services.processor.models import Capture, CaptureSet

logger = logging.getLogger(name=None)


def test_export_includes_image_preview_capture_id():
    jm = JobModelImage(
        SingleImageConfigurationSet(
            jobcontrol=SingleImageJobControl(),
            processing=SingleImageProcessing(),
            trigger=Trigger(),
        ),
        Mock(spec=AcquisitionService),
    )
    capture = Capture(filepath=Path("capture.jpg"))
    jm._capture_sets.append(CaptureSet([capture]))

    assert jm.export().preview_capture_id == str(capture.uuid)


def test_on_enter_capture_moves_capture_to_original(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    jm = JobModelImage(
        SingleImageConfigurationSet(
            jobcontrol=SingleImageJobControl(),
            processing=SingleImageProcessing(),
            trigger=Trigger(),
        ),
        Mock(spec=AcquisitionService),
    )
    capture_path = tmp_path / "capture.jpg"
    capture_path.write_bytes(b"capture")
    original_dir = tmp_path / "originals"
    original_dir.mkdir()
    monkeypatch.setattr(processor_base, "PATH_CAMERA_ORIGINAL", str(original_dir))
    # pyrefly: ignore[missing-attribute]
    jm._acquisition_service.wait_for_still_file.return_value = capture_path

    jm.on_enter_capture()

    capture = jm._capture_sets[0].captures[0]
    assert capture.filepath.parent == original_dir
    assert capture.filepath.is_file()
    assert not capture_path.exists()
    assert jm.export().preview_capture_id == str(capture.uuid)


def test_complete_phase1image_uses_captured_original(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    jm = JobModelImage(
        SingleImageConfigurationSet(
            jobcontrol=SingleImageJobControl(),
            processing=SingleImageProcessing(),
            trigger=Trigger(),
        ),
        Mock(spec=AcquisitionService),
    )
    original_dir = tmp_path / "originals"
    original_dir.mkdir()
    capture_path = original_dir / "capture.jpg"
    capture_path.write_bytes(b"capture")
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    cached_path = tmp_path / "cached.jpg"
    cached_path.write_bytes(b"cached")
    monkeypatch.setattr(processor_base, "PATH_CAMERA_ORIGINAL", str(original_dir))
    monkeypatch.setattr(processor_base, "PATH_PROCESSED", str(processed_dir))
    monkeypatch.setattr(jm._cache, "get_cached_repr", Mock(return_value=SimpleNamespace(filepath=cached_path)))

    def process_images(_filepath: Path, mediaitem):
        assert capture_path.is_file()
        mediaitem.processed.write_bytes(b"processed")

    monkeypatch.setattr(processor_base, "process_phase1images", process_images)
    mediaitem = jm.complete_phase1image(capture_path, True, SingleImageProcessing())

    assert capture_path == mediaitem.captured_original


@pytest.fixture(scope="module")
def _acqs() -> Generator[AcquisitionService, None, None]:
    acqs = AcquisitionService()
    acqs.start()
    yield acqs
    acqs.stop()


def test_jobmodel_start_count(_acqs: AcquisitionService):
    countdown_time = 1
    offset = 0.25
    expected_blocking_time = countdown_time - offset

    jm = JobModelImage(
        SingleImageConfigurationSet(
            jobcontrol=SingleImageJobControl(countdown_capture=countdown_time),
            processing=SingleImageProcessing(),
            trigger=Trigger(),
        ),
        _acqs,
    )

    jm.start_countdown(offset)

    start_time = time.perf_counter()
    jm.wait_countdown_finished()
    end_time = time.perf_counter()

    actual_blocking_time = end_time - start_time

    assert pytest.approx(expected_blocking_time, abs=0.2) == actual_blocking_time  # 0.2 is acceptable tolerance for any inaccuracies


def test_jobmodel_start_count_zero(_acqs: AcquisitionService):
    countdown_time = 0
    offset = 0
    expected_blocking_time = countdown_time - offset

    jm = JobModelImage(
        SingleImageConfigurationSet(
            jobcontrol=SingleImageJobControl(countdown_capture=countdown_time),
            processing=SingleImageProcessing(),
            trigger=Trigger(),
        ),
        _acqs,
    )

    jm.start_countdown(offset)

    start_time = time.time()
    jm.wait_countdown_finished()
    end_time = time.time()

    actual_blocking_time = (end_time - start_time) - expected_blocking_time

    assert abs(actual_blocking_time) < (0.1)  # 0.1 is acceptable tolerance for any inaccuracies


def test_jobmodel_start_count_equal(_acqs: AcquisitionService):
    countdown_time = 1
    offset = 1
    expected_blocking_time = countdown_time - offset

    jm = JobModelImage(
        SingleImageConfigurationSet(
            jobcontrol=SingleImageJobControl(countdown_capture=countdown_time),
            processing=SingleImageProcessing(),
            trigger=Trigger(),
        ),
        _acqs,
    )

    jm.start_countdown(offset)

    start_time = time.time()
    jm.wait_countdown_finished()
    end_time = time.time()

    actual_blocking_time = (end_time - start_time) - expected_blocking_time

    assert abs(actual_blocking_time) < (0.1)  # 0.1 is acceptable tolerance for any inaccuracies


def test_jobmodel_start_count_bigger_offset(_acqs: AcquisitionService):
    countdown_time = 1
    offset = 2
    expected_blocking_time = 0  # in this case due to camera delay longer than actual countdown, the blocking time is skipped.

    jm = JobModelImage(
        SingleImageConfigurationSet(
            jobcontrol=SingleImageJobControl(countdown_capture=countdown_time),
            processing=SingleImageProcessing(),
            trigger=Trigger(),
        ),
        _acqs,
    )

    jm.start_countdown(offset)

    start_time = time.time()
    jm.wait_countdown_finished()
    end_time = time.time()

    actual_blocking_time = (end_time - start_time) - expected_blocking_time

    assert abs(actual_blocking_time) < (0.1)  # 0.1 is acceptable tolerance for any inaccuracies
