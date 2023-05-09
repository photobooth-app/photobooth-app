@echo off

REM in windows, can be started as normal user

REM change working directory to where this script lives in
cd %~dp0

REM remove cache files to avoid using old bytecode during dev
python -Bc "for p in __import__('pathlib').Path('.').rglob('*.py[co]'): p.unlink()"
python -Bc "for p in __import__('pathlib').Path('.').rglob('__pycache__'): p.rmdir()"

REM start application
REM -O for optimized, means all "assert" statement are removed from bytecode
python -O -m photobooth
