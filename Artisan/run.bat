@echo off
REM Double-click this file to start Artisan Geo (uses the project's .venv).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating the virtual environment and installing packages - first time only...
  python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
".venv\Scripts\python.exe" run.py
pause
