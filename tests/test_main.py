"""
Testing Simulated Backend
"""
import logging
import threading
import time

import pytest
import uvicorn

logger = logging.getLogger(name=None)


def test_main_package():
    from photobooth import __main__

    server = __main__.main()
    assert isinstance(server, uvicorn.Server)


def test_singleinstance():
    from photobooth import __main__

    def instance1_function():
        server1 = __main__.main()
        assert isinstance(server1, uvicorn.Server)
        # emulate the thread is living some time, so server1 blocks server2 to start
        time.sleep(10)

    instance1_thread = threading.Thread(target=instance1_function, daemon=True)
    instance1_thread.start()

    # give app some time to start up and block the port
    time.sleep(5)

    # server2 is expected to SystemExit, this is tested here
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        server2 = __main__.main()
        assert isinstance(server2, uvicorn.Server)

    # wait for thread to finish but max 1 sec. we have all results at this point, so we can time out and it's fine
    instance1_thread.join(timeout=1)

    # ensure sys.exit with value -1 was raised by server2
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == -1
