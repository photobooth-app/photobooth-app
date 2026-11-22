import logging
import os
import shutil
from collections.abc import Generator
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

import pytest
import requests

from photobooth import PATH_CAMERA_ORIGINAL, PATH_PROCESSED
from photobooth.database.models import Mediaitem
from photobooth.plugins.synchronizer.config import SynchronizerConfig
from photobooth.plugins.synchronizer.shareondemand import ShareOnDemandService
from photobooth.plugins.synchronizer.synchronizer import RcloneApi
from photobooth.services.mediacollection.database import Database
from photobooth.utils.helper import filename_str_time

logger = logging.getLogger(name=None)

if os.getenv("synchronizer-ondemandshareconfig__apikey") is None:
    pytest.skip("Skipping ShareOnDemand tests outside Linux CI job", allow_module_level=True)


@pytest.fixture(scope="function")
def sod_srv():

    rclone = RcloneApi()
    rclone.start()
    rclone.wait_until_operational()

    cfg = SynchronizerConfig().ondemandshareconfig

    s = ShareOnDemandService(
        rclone,
        cfg.name,
        cfg.subdir,
        cfg.baseurl,
        cfg.apikey,
    )

    s.start()
    assert s.operational_flag.wait(timeout=5)

    yield s

    s.stop()


@pytest.fixture(params=["png", "jpg", "gif", "webp", "avif", "mp4"])
def _mediaitem(request) -> Generator[Mediaitem, None, None]:

    mime_headers = {
        "png": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00",
        "jpg": b"\xff\xd8\xff\xdb",
        "gif": b"GIF89a",
        "webp": b"RIFF\x2a\x00\x00\x00WEBP",
        "avif": b"\x00\x00\x00\x1cftypavif",
        "mp4": b"\x00\x00\x00\x18ftypmp42",
    }

    dummy_file_path = Path(
        NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=PATH_CAMERA_ORIGINAL,
            prefix=f"{filename_str_time()}_pytest_dummy_",
            suffix=f".{request.param}",
        ).name  # name from namedtemporaryfile is the whole path.
    )

    dummy_file_path_original = dummy_file_path.relative_to(Path.cwd())

    dummy_file_path_original.write_bytes(mime_headers[request.param])

    shutil.copy(dummy_file_path_original, PATH_PROCESSED)

    new_item_instance = Mediaitem(
        job_identifier=uuid4(),
        media_type="image",
        captured_original=dummy_file_path_original,
        processed=Path(PATH_PROCESSED, dummy_file_path_original.name),
        pipeline_config={},
        show_in_gallery=True,
    )

    db = Database()
    db.add_item(new_item_instance)
    assert new_item_instance.id

    yield new_item_instance

    db.delete_item(new_item_instance)


def test_shareondemand_urls_valid(sod_srv: ShareOnDemandService):
    """test some common actions on url"""

    # /api.php
    r = requests.get(sod_srv.shareservice_api_php_url)

    assert r.json()  # ensure we can decode every answer as json
    assert r.status_code == 400

    # info action
    r = requests.get(sod_srv.shareservice_api_php_url, params={"action": "version"})
    logger.info(f"{r.text=}")
    assert r.json()  # ensure we can decode every answer as json
    assert r.status_code == 200

    # invalid action
    r = requests.get(sod_srv.shareservice_api_php_url, params={"action": "nonexistentaction"})
    logger.info(f"{r.text=}")
    assert r.json()  # ensure we can decode every answer as json
    assert r.status_code == 400

    # invalid apikey
    r = requests.post(
        sod_srv.shareservice_api_php_url,
        files=None,
        data={
            "action": "upload",
            "apikey": "wrongapikeyprovided",
            "id": "invalididdoesntmatteranyway",
        },
    )
    logger.info(f"{r.text=}")
    assert r.json()  # ensure we can decode every answer as json
    assert r.status_code == 401


def test_shareondemand_download_all_mediaitem_types(sod_srv: ShareOnDemandService, _mediaitem: Mediaitem):
    """start service and try to download an image"""

    logger.info(f"check to download {_mediaitem.id=}, {_mediaitem.media_type=}")
    r = requests.get(
        sod_srv.shareservice_api_php_url,
        params={"action": "download", "id": str(_mediaitem.id)},
    )

    # valid status code
    assert r.status_code == 200, f"Server returned {r.status_code}: {r.text}"

    # check we received the same file via php api
    with open(_mediaitem.processed, "rb") as f:
        assert r.content == f.read()


def test_shareondemand_download_revisions(sod_srv: ShareOnDemandService, _mediaitem: Mediaitem):
    params = {"action": "download", "id": str(_mediaitem.id), "rev": "0"}
    original = _mediaitem.processed.read_bytes()

    first = requests.get(sod_srv.shareservice_api_php_url, params=params)
    assert first.status_code == 200
    assert first.content == original

    updated = original + b"updated"
    _mediaitem.processed.write_bytes(updated)
    second = requests.get(sod_srv.shareservice_api_php_url, params=params | {"rev": "1"})
    assert second.status_code == 200
    assert second.content == updated

    cached = requests.get(sod_srv.shareservice_api_php_url, params=params)
    assert cached.status_code == 200
    assert cached.content == original

    invalid = requests.get(sod_srv.shareservice_api_php_url, params=params | {"rev": "../1"})
    assert invalid.status_code == 500
    assert invalid.json()["detail"] == "Invalid revision"


def test_shareondemand_download_nonexistant_image(sod_srv: ShareOnDemandService):
    """start service and try to download an image that does not exist"""

    r = requests.get(
        sod_srv.shareservice_api_php_url,
        params={"action": "download", "id": uuid4().hex},
    )

    # valid status code is 500 because image not existing.
    assert r.status_code == 500
    assert r.json()
