@echo off
setlocal
cd /d %~dp0

where npm >nul 2>nul
if errorlevel 1 (
  echo npm not found, please install Node.js and add to PATH
  pause
  exit /b 1
)

where mvn >nul 2>nul
if errorlevel 1 (
  echo mvn not found, please install Maven and add to PATH
  pause
  exit /b 1
)

taskkill /F /IM node.exe /T >nul 2>nul
taskkill /F /IM java.exe /T >nul 2>nul

start "backend" powershell -NoExit -Command "Set-Location '%~dp0backend'; mvn spring-boot:run"
start "frontend" powershell -NoExit -Command "Set-Location '%~dp0frontend'; npm run dev"

timeout /t 8 >nul
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:5173' -UseBasicParsing -TimeoutSec 3; if ($r.StatusCode -ge 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
if errorlevel 1 (
  echo Frontend failed to start, check the frontend window for errors
  pause
  exit /b 1
)

echo Services started:
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8080
echo If pages still not working, check backend/frontend window errors
pause
exit /b 0
