@echo off
setlocal
cd /d "%~dp0"

if not exist "backend\requirements.txt" (
  if exist "savvpro-test-voice-agent\backend\requirements.txt" (
    cd /d "%~dp0savvpro-test-voice-agent"
  )
)

where docker >nul 2>nul
if errorlevel 1 (
  echo Docker is not installed or not on PATH.
  echo Install Docker Desktop, then re-run this file.
  pause
  exit /b 1
)

echo === Harbor Lights — Docker Compose ===
echo UI will be http://localhost:8080
echo API will be http://localhost:8000
echo Admin password default: admin
echo.
docker compose up --build
