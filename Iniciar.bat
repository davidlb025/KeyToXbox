@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Crea primero el entorno virtual siguiendo las instrucciones de README.md.
  pause
  exit /b 1
)
.venv\Scripts\python.exe main.py
if errorlevel 1 pause
