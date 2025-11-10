import logging
import shutil
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import patch
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy.orm.attributes import flag_modified

from photobooth import PATH_CAMERA_ORIGINAL, PATH_PROCESSED, PATH_UNPROCESSED
from photobooth.database.models import Mediaitem, MediaitemTypes
from photobooth.services.collection import MediacollectionService
from photobooth.utils.helper import filename_str_time

logger = logging.getLogger(name=None)


@pytest.fixture()
def cs():
    # setup
    cs = MediacollectionService()

    yield cs


@pytest.fixture()
def dummy_item():
    img = Image.new("RGB", (600, 400), color="grey")
    img_path_original = Path(
        NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=PATH_CAMERA_ORIGINAL,
            prefix=f"{filename_str_time()}_pytest_dummy_",
            suffix=".jpg",
        ).name  # name from namedtemporaryfile is the whole path.
    )
    # absolute path's dont work for us, make it relative to home.
    img_path_original = img_path_original.relative_to(Path.cwd())

    img.save(img_path_original)
    shutil.copy(img_path_original, PATH_PROCESSED)
    shutil.copy(img_path_original, PATH_UNPROCESSED)

    new_item_instance = Mediaitem(
        job_identifier=uuid4(),
        media_type=MediaitemTypes.image,
        captured_original=img_path_original,
        unprocessed=Path(PATH_UNPROCESSED, img_path_original.name),
        processed=Path(PATH_PROCESSED, img_path_original.name),
        pipeline_config={},
        show_in_gallery=True,
    )

    yield new_item_instance


def test_start_maintain(cs: MediacollectionService):
    with patch.object(cs, "on_start_maintain") as mock:
        cs.start()

        mock.assert_called()


def test_start_stop(cs: MediacollectionService):
    cs.start()
    cs.stop()
    cs.stop()


def test_maintain(cs: MediacollectionService):
    cs.on_start_maintain()


def test_add_item(cs: MediacollectionService, dummy_item: Mediaitem):
    count_before = cs.count()

    cs.add_item(dummy_item)

    assert count_before + 1 == cs.count()


def test_add_item_filedoesntexist(cs: MediacollectionService):
    count_before = cs.count()

    with pytest.raises(FileNotFoundError):
        cs.add_item(
            Mediaitem(
                job_identifier=uuid4(),
                media_type=MediaitemTypes.image,
                unprocessed=Path("./src/tests/assets/input.jpg"),
                processed=Path("./src/tests/assets/input_nonexistant.jpg"),
                pipeline_config={},
                show_in_gallery=True,
            )
        )

    with pytest.raises(FileNotFoundError):
        cs.add_item(
            Mediaitem(
                job_identifier=uuid4(),
                media_type=MediaitemTypes.image,
                unprocessed=Path("./src/tests/assets/input_nonexistant.jpg"),
                processed=Path("./src/tests/assets/input.jpg"),
                pipeline_config={},
                show_in_gallery=True,
            )
        )

    assert count_before == cs.count()


def test_update_item(cs: MediacollectionService, dummy_item: Mediaitem):
    cs.add_item(dummy_item)
    updated_at_before_update = dummy_item.updated_at

    # "simulate" a change, so the item is updated actually in the db.
    flag_modified(dummy_item, "pipeline_config")
    # time is only precise for 1 second in db so we need to wait a bit until updating actually
    time.sleep(1.5)

    cs.update_item(dummy_item)

    assert dummy_item.updated_at > updated_at_before_update


def test_update_item_nochange_no_updated_at(cs: MediacollectionService, dummy_item: Mediaitem):
    cs.add_item(dummy_item)
    updated_at_before_update = dummy_item.updated_at

    cs.update_item(dummy_item)

    assert dummy_item.updated_at == updated_at_before_update


def test_delete_item(cs: MediacollectionService, dummy_item: Mediaitem):
    cs.add_item(dummy_item)
    count_before = cs.count()

    cs.delete_item(dummy_item)

    assert count_before - 1 == cs.count()
