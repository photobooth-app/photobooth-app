import logging

import pytest

from photobooth.plugins.filter_pilgram2.config import FilterPilgram2Config
from photobooth.plugins.filter_pilgram2.filter_pilgram2 import FilterPilgram2

logger = logging.getLogger(name=None)


@pytest.fixture()
def filter_pilgram2_plugin():
    # setup
    plgrm2 = FilterPilgram2()

    plgrm2._config = FilterPilgram2Config()

    yield plgrm2
