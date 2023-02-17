#!/bin/bash

# change working directory to where this script lives in https://stackoverflow.com/questions/6393551/what-is-the-meaning-of-0-in-a-bash-script
cd "${0%/*}"


# remove cache files to avoid using old bytecode during dev
python -Bc "for p in __import__('pathlib').Path('.').rglob('*.py[co]'): p.unlink()"
python -Bc "for p in __import__('pathlib').Path('.').rglob('__pycache__'): p.rmdir()"

# start application
# -O for optimized, means all "assert" statement are removed from bytecode
python -O ./start.py
