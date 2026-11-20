@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First follow SOURCE_PREVIEW.md to create .venv and install requirements.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" preview.py %*
