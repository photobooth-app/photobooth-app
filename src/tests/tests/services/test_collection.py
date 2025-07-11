import logging
import time
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.orm.attributes import flag_modified

from photobooth.database.models import Mediaitem, MediaitemTypes
from photobooth.services.collection import MediacollectionService
from photobooth.services.synchronizer.synchronizer import Synchronizer

logger = logging.getLogger(name=None)


@pytest.fixture()
def cs():
    # setup
    cs = MediacollectionService(Synchronizer())

    yield cs


@pytest.fixture()
def dummy_item(cs: MediacollectionService):
    borrow_to_lend_files_from = cs.get_item_latest()
    new_item_instance = Mediaitem(
        job_identifier=uuid4(),
        media_type=MediaitemTypes.image,
        captured_original=borrow_to_lend_files_from.captured_original,
        unprocessed=borrow_to_lend_files_from.unprocessed,
        processed=borrow_to_lend_files_from.processed,
        pipeline_config={},
        show_in_gallery=True,
    )
    logger.warning(new_item_instance)

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
