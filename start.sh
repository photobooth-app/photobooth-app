#!/bin/bash

# needs sudo rights

# remove cache files
rm -r ./__pycache__ 2> /dev/null
rm -r ./lib/__pycache__ 2> /dev/null
rm -r ./utils/__pycache__ 2> /dev/null

# start application
python3 ./imageserver.py
