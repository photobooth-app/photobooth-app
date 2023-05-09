import os
import sys
import pytest

# https://docs.python-guide.org/writing/structure/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))



def test_chose_1pic():
    from start import imageServers
    from start import processingpicture
    from start import evt_chose_1pic_get

    processingpicture._reset()
    imageServers.start()

    evt_chose_1pic_get()

    # occupy statemachine for next test
    processingpicture.thrill()
    with pytest.raises(RuntimeError):
        evt_chose_1pic_get()

    # reset statemachine for next test
    processingpicture._reset()

    evt_chose_1pic_get()

    imageServers.stop()
