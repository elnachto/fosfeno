@echo off
setlocal
cd /d "%~dp0"
python jarvis.py --motor nemotron %*
if errorlevel 1 pause
