#!/bin/bash

# needs sudo rights

# change working directory to where this script lives in https://stackoverflow.com/questions/6393551/what-is-the-meaning-of-0-in-a-bash-script
cd "${0%/*}"


# remove cache files
rm -r ./__pycache__ 2> /dev/null
rm -r ./lib/__pycache__ 2> /dev/null
rm -r ./utils/__pycache__ 2> /dev/null

# start application
# -O for optimized, means all "assert" statement are removed from bytecode
python3 -O ./imageserver.py
