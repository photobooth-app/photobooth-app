"""
Given text files or text from stdin, simulates keyboard events that type the
text character-by-character.
"""
import sys

sys.path.append('../')
import fileinput

import keyboard

for line in fileinput.input():
	keyboard.write(line)
