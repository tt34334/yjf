$ErrorActionPreference = "SilentlyContinue"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Get-Process java -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force

if (-not (Get-Command mvn -ErrorAction SilentlyContinue)) {
  Write-Host "mvn not found, please install Maven and add to PATH" -ForegroundColor Red
  exit 1
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  Write-Host "npm not found, please install Node.js and add to PATH" -ForegroundColor Red
  exit 1
}

Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$ProjectRoot\backend'; mvn spring-boot:run"
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$ProjectRoot\frontend'; npm run dev"

Start-Sleep -Seconds 8

$backendOk = $false
$frontendOk = $false

for ($i = 0; $i -lt 20; $i++) {
  try {
    $b = Invoke-WebRequest -Uri "http://localhost:8080/api/professionals/coaches" -UseBasicParsing -TimeoutSec 2
    if ($b.StatusCode -ge 200 -and $b.StatusCode -lt 500) { $backendOk = $true }
  } catch {}

  try {
    $f = Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing -TimeoutSec 2
    if ($f.StatusCode -ge 200 -and $f.StatusCode -lt 500) { $frontendOk = $true }
  } catch {}

  if ($backendOk -and $frontendOk) { break }
  Start-Sleep -Seconds 2
}

if ($backendOk -and $frontendOk) {
  Write-Host "Services started: Frontend http://localhost:5173 , Backend http://localhost:8080" -ForegroundColor Green
  exit 0
}

if (-not $backendOk) {
  Write-Host "Backend failed to start, check the backend window for errors (common cause: MySQL not running)" -ForegroundColor Red
}
if (-not $frontendOk) {
  Write-Host "Frontend failed to start, check the frontend window for errors" -ForegroundColor Red
}

exit 1
