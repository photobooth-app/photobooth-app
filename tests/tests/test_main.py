"""
Testing main
"""

import logging

logger = logging.getLogger(name=None)


def test_main_instance():
    from photobooth.__main__ import main

    main(False)
