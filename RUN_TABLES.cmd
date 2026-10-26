@echo off
setlocal
cd /d "%~dp0"
set "DOCFUSE_RUN_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "DOCFUSE_RUN_PYTHON=%~dp0.venv\Scripts\python.exe"
if defined DOCFUSE_PYTHON set "DOCFUSE_RUN_PYTHON=%DOCFUSE_PYTHON%"
echo Checking recorded results. No model inference is required.
"%DOCFUSE_RUN_PYTHON%" -u "scripts\reproduce_results.py"
if errorlevel 1 (
  echo.
  echo The command failed. Read the error above.
  echo For plotting dependencies, run: python -m pip install -r requirements-figures.txt
  pause
  exit /b 1
)
echo.
echo Completed.
pause
