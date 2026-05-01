@echo off
setlocal
cd /d "%~dp0"
title Aeon-V1 Terminal

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 scripts\aeon_chat.py --base-path "%~dp0"
) else (
  python scripts\aeon_chat.py --base-path "%~dp0"
)

if errorlevel 1 (
  echo.
  echo Aeon chat exited with an error.
)

echo.
pause
