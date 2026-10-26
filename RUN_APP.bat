@echo off
setlocal
cd /d "%~dp0"

REM If this folder only wraps another copy, dive in
if not exist "backend\requirements.txt" (
  if exist "savvpro-test-voice-agent\backend\requirements.txt" (
    cd /d "%~dp0savvpro-test-voice-agent"
  )
)

echo === Harbor Lights — starting backend + frontend ===
echo.

if not exist "backend\.venv\Scripts\python.exe" (
  echo Creating Python venv...
  py -3 -m venv backend\.venv 2>nul || python -m venv backend\.venv
  call backend\.venv\Scripts\activate.bat
  pip install -r backend\requirements.txt
) else (
  call backend\.venv\Scripts\activate.bat
)

if not exist "frontend\node_modules" (
  echo Installing frontend deps...
  pushd frontend
  call npm install
  popd
)

start "Harbor API" cmd /k "cd /d "%CD%\backend" && call .venv\Scripts\activate.bat && uvicorn app.main:app --reload --port 8000"
timeout /t 3 /nobreak >nul
start "Harbor UI" cmd /k "cd /d "%CD%\frontend" && npm run dev"
timeout /t 4 /nobreak >nul
start "" http://localhost:5173

echo.
echo API:  http://localhost:8000
echo UI:   http://localhost:5173
echo Admin:http://localhost:5173/#/admin  (password: admin)
echo Keep the two black windows open.
echo.
pause
