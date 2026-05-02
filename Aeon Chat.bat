@echo off
setlocal
cd /d "%~dp0"
title Aeon-V1 Terminal

if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" "%CD%\scripts\aeon_chat.py" --base-path "%CD%"
) else (
  where py >nul 2>nul
  if %ERRORLEVEL%==0 (
  py -3 "%CD%\scripts\aeon_chat.py" --base-path "%CD%"
) else (
  python "%CD%\scripts\aeon_chat.py" --base-path "%CD%"
  )
)

if errorlevel 1 (
  echo.
  echo Aeon chat exited with an error.
)

echo.
pause
