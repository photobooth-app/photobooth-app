import logging
import subprocess
import sys
from unittest.mock import patch

import pytest

from photobooth.services.sseservice import SseService
from photobooth.services.systemservice import SystemService

logger = logging.getLogger(name=None)


@pytest.mark.skipif(not sys.platform == "linux", reason="requires linux platform")
def test_systemd_control():
    systemservice: SystemService = SystemService(SseService())

    with patch.object(subprocess, "run"):
        systemservice.util_systemd_control("start")
        subprocess.run.assert_called()
