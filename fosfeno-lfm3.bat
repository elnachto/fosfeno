@echo off
setlocal
cd /d "%~dp0"
python jarvis.py --motor lfm3 %*
if errorlevel 1 pause
