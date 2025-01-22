"""
Testing main
"""

import logging

logger = logging.getLogger(name=None)


def test_main_instance():
    import photobooth.__main__

    photobooth.__main__.main([], run_server=False)
