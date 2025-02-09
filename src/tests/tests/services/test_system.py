import logging
import subprocess
import sys
from unittest.mock import patch

import pytest

from photobooth.services.system import SystemService

logger = logging.getLogger(name=None)


@pytest.mark.skipif(not sys.platform == "linux", reason="requires linux platform")
def test_systemd_control():
    systemservice: SystemService = SystemService()

    with patch.object(subprocess, "run") as mock:
        systemservice.util_systemd_control("start")
        mock.assert_called()
