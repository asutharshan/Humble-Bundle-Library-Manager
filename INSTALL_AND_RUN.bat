@echo off
setlocal EnableExtensions
title Media Utility v2.1 Installer
color 0B

echo ==========================================================================
echo   Media Utility v2.1
echo   Arun Sutharshan - 06 October 2026
echo   Authorised-use media management utility
echo ==========================================================================
echo.

set "PY="

where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m pip --version >nul 2>nul
    if not errorlevel 1 set "PY=py -3"
)

if not defined PY (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -m pip --version >nul 2>nul
        if not errorlevel 1 set "PY=python"
    )
)

if not defined PY (
    where py >nul 2>nul
    if not errorlevel 1 (
        echo Python found but pip is missing. Trying ensurepip...
        py -3 -m ensurepip --upgrade
        py -3 -m pip --version >nul 2>nul
        if not errorlevel 1 set "PY=py -3"
    )
)

if not defined PY goto :python_problem

echo [1/5] Python:
%PY% --version

echo.
echo [2/5] Updating pip...
%PY% -m pip install --upgrade pip
if errorlevel 1 goto :install_error

echo.
echo [3/5] Installing/updating Media Utility dependencies...
echo       yt-dlp default package includes the supported EJS challenge solver.
%PY% -m pip install --upgrade "yt-dlp[default]" imageio-ffmpeg
if errorlevel 1 goto :install_error

echo.
echo [4/5] Checking Deno JavaScript runtime...
where deno >nul 2>nul
if not errorlevel 1 goto :deno_ok

if exist "%USERPROFILE%\.deno\bin\deno.exe" goto :deno_ok

echo Deno was not found. Media Utility will try to install it automatically.
echo.

where winget >nul 2>nul
if errorlevel 1 goto :try_deno_script

echo Trying Windows Package Manager...
winget install --id DenoLand.Deno -e --accept-package-agreements --accept-source-agreements
if not errorlevel 1 goto :deno_postinstall

:try_deno_script
echo winget installation was unavailable or unsuccessful.
echo Trying Deno's official PowerShell installer...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { irm https://deno.land/install.ps1 | iex; exit 0 } catch { Write-Host $_; exit 1 }"
if errorlevel 1 goto :deno_warning

:deno_postinstall
if exist "%USERPROFILE%\.deno\bin\deno.exe" goto :deno_ok
where deno >nul 2>nul
if not errorlevel 1 goto :deno_ok

:deno_warning
echo.
echo [WARNING] Deno could not be installed automatically.
echo YouTube may still work for some links, but modern YouTube extraction can
echo require Deno 2.3+ for JavaScript challenge solving.
echo Media Utility will show "Deno: NOT FOUND" until it is installed.
echo.
goto :tk_check

:deno_ok
echo Deno is available.
if exist "%USERPROFILE%\.deno\bin\deno.exe" "%USERPROFILE%\.deno\bin\deno.exe" --version
where deno >nul 2>nul
if not errorlevel 1 deno --version

:tk_check
echo.
echo [5/5] Checking Tkinter...
%PY% -c "import tkinter" >nul 2>nul
if errorlevel 1 goto :tk_error

echo.
echo Starting Media Utility v2.1...
%PY% "%~dp0media_utility.py"
if errorlevel 1 (
    echo.
    echo The application exited with an error.
    pause
)
goto :end

:python_problem
echo.
echo [ERROR] No complete Python installation with pip was found.
echo Install/repair the standard Python distribution and include:
echo   - pip
echo   - tcl/tk and IDLE
echo   - Python Launcher
echo   - Add Python to PATH
pause
exit /b 2

:tk_error
echo.
echo [ERROR] Tkinter is missing.
echo Modify/reinstall Python and select "tcl/tk and IDLE".
pause
exit /b 3

:install_error
echo.
echo [ERROR] Dependency installation failed.
echo Check internet/proxy/firewall access.
pause
exit /b 4

:end
endlocal
