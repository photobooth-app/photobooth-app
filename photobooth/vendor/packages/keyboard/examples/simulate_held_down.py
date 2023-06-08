import time

import keyboard

# Sends 20 "key down" events in 0.1 second intervals, followed by a single
# "key up" event.
for _i in range(20):
    keyboard.press('a')
    time.sleep(0.1)
keyboard.release('a')
