@echo off
setlocal
cd /d "%~dp0"

if not exist "backend\requirements.txt" (
  if exist "savvpro-test-voice-agent\backend\requirements.txt" (
    cd /d "%~dp0savvpro-test-voice-agent"
  )
)

if not exist "backend\.venv\Scripts\python.exe" (
  echo Creating Python venv...
  py -3 -m venv backend\.venv 2>nul || python -m venv backend\.venv
  call backend\.venv\Scripts\activate.bat
  pip install -r backend\requirements.txt
) else (
  call backend\.venv\Scripts\activate.bat
)

cd backend
pytest -v
echo.
pause
