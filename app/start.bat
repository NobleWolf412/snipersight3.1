@echo off
rem SniperSight launcher: watchdog supervises scanner + server (auto-restart).
cd /d "%~dp0"
start "" http://localhost:8422
python -X utf8 watchdog.py
