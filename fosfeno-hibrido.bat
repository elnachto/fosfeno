@echo off
setlocal
cd /d "%~dp0"
python jarvis.py --motor hibrido %*
if errorlevel 1 pause
