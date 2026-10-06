@echo off
setlocal
title Build Media Utility v2.1.1 EXE
color 0A

where py >nul 2>nul
if not errorlevel 1 (
    set "PY=py -3"
) else (
    set "PY=python"
)

echo Installing/updating build dependencies...
%PY% -m pip install --upgrade pyinstaller "yt-dlp[default]" imageio-ffmpeg
if errorlevel 1 goto :error

echo.
echo Building MediaUtility.exe...
%PY% -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name "MediaUtility" ^
  --collect-all yt_dlp ^
  --collect-all yt_dlp_ejs ^
  --collect-all imageio_ffmpeg ^
  "%~dp0media_utility.py"

if errorlevel 1 goto :error

echo.
echo Build complete:
echo   %~dp0dist\MediaUtility.exe
echo.
echo NOTE: Deno remains an external runtime and should be installed on the
echo destination machine for reliable modern YouTube extraction.
pause
goto :end

:error
echo Build failed.
pause
exit /b 1

:end
endlocal
