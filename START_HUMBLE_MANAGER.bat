@echo off
setlocal
cd /d "%~dp0"
title Humble Library Manager v2.0
echo Installing/checking requirements...
py -m pip install -r requirements.txt
if errorlevel 1 (echo Python/dependency setup failed.& pause& exit /b 1)
echo Starting at http://127.0.0.1:8765
echo Keep this window open while using the manager.
py app.py
pause
