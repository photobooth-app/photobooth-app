import logging

logger = logging.getLogger(name=None)


def test_app():
    import photobooth.application

    photobooth.application._create_app()
