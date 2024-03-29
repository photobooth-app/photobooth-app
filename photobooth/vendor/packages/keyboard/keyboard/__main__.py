import fileinput
import json
import sys

import keyboard


def print_event_json(event):
    print(event.to_json(ensure_ascii=sys.stdout.encoding != 'utf-8'))
    sys.stdout.flush()
keyboard.hook(print_event_json)

def parse_event_json(line):
    return keyboard.KeyboardEvent(**json.loads(line))
keyboard.play(parse_event_json(line) for line in fileinput.input())
