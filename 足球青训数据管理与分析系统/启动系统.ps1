# 足球青训数据管理系统 - 一键启动器（PowerShell 版）
# 双击"启动系统.bat"会调用此脚本

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
$Host.UI.RawUI.WindowTitle = "足球青训系统_主控"

function Write-Step($num, $msg) {
    Write-Host "[$num/6] $msg" -ForegroundColor Green
}
function Write-Err($msg) {
    Write-Host "[错误] $msg" -ForegroundColor Red
}
function Write-Warn2($msg) {
    Write-Host "[警告] $msg" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   足球青训数据管理系统  -  一键启动器" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ---------- 1. 检查 Python ----------
$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) {
    Write-Err "未检测到 Python，请先安装 Python 3.10+"
    Write-Host "       下载: https://www.python.org/downloads/"
    Write-Host "       安装时务必勾选 'Add Python to PATH'"
    Read-Host "按回车键退出"
    exit 1
}
$pyVer = & python --version 2>&1
Write-Step 1 "检测到 $pyVer"

# ---------- 2. 虚拟环境 ----------
$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Step 2 "创建虚拟环境..."
    & python -m venv ".venv"
    if (-not (Test-Path $venvPython)) {
        Write-Err "虚拟环境创建失败"
        Read-Host "按回车键退出"
        exit 1
    }
} else {
    Write-Step 2 "虚拟环境已存在"
}

# 激活虚拟环境（用 activate.ps1）
$activateScript = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    & $activateScript
} else {
    # 回退：直接用 venv 的 python
    $env:PATH = "$ProjectRoot\.venv\Scripts;$env:PATH"
}

# ---------- 3. 依赖检查与安装 ----------
$depsOk = $true
try {
    & python -c "import fastapi, streamlit, plotly, pandas" 2>$null
    if ($LASTEXITCODE -ne 0) { $depsOk = $false }
} catch { $depsOk = $false }

if (-not $depsOk) {
    Write-Step 3 "首次启动，安装依赖中（约1-3分钟，请耐心等待）..."
    & python -m pip install --upgrade pip -q
    & pip install -r requirements.txt -q
    if ($LASTEXITCODE -ne 0) {
        Write-Warn2 "官方源安装失败，尝试国内镜像源..."
        & pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
        if ($LASTEXITCODE -ne 0) {
            Write-Err "依赖安装失败，请检查网络"
            Read-Host "按回车键退出"
            exit 1
        }
    }
    Write-Host "       依赖安装完成"
} else {
    Write-Step 3 "依赖已就绪"
}

# ---------- 4. 配置文件 ----------
$envFile = Join-Path $ProjectRoot ".env"
if (-not (Test-Path $envFile)) {
    Write-Step 4 "生成默认配置（使用 SQLite，无需安装 MySQL）..."
    @"
DATABASE_URL=sqlite:///./academy.db
REDIS_URL=redis://localhost:6379/0
APP_NAME=足球青训数据管理 API
DEBUG=true
EXPORT_DIR=./exports
"@ | Out-File -FilePath $envFile -Encoding UTF8
    $exportsDir = Join-Path $ProjectRoot "exports"
    if (-not (Test-Path $exportsDir)) { New-Item -ItemType Directory -Path $exportsDir | Out-Null }
} else {
    Write-Step 4 "配置文件 .env 已存在"
}

# ---------- 5. 数据库初始化 ----------
Write-Step 5 "检查数据库..."
$dbFile = Join-Path $ProjectRoot "academy.db"
$needSeed = $false
if (-not (Test-Path $dbFile)) {
    Write-Host "       首次启动，初始化数据库和种子数据..."
    $needSeed = $true
} else {
    # 检查 players 表是否有数据
    try {
        $result = & python -c "import sqlite3; con=sqlite3.connect('academy.db'); cur=con.cursor(); cur.execute('SELECT count(*) FROM players'); print(cur.fetchone()[0])" 2>$null
        if ($result -and [int]$result -gt 0) {
            Write-Host "       数据库已就绪"
        } else {
            Write-Host "       数据库无数据，重新生成种子数据..."
            $needSeed = $true
        }
    } catch {
        Write-Host "       数据库检查异常，尝试重新初始化..."
        $needSeed = $true
    }
}
if ($needSeed) {
    & python -m app.seed
    if ($LASTEXITCODE -ne 0) {
        Write-Warn2 "种子数据初始化异常，但服务仍会尝试启动"
    }
}

# ---------- 6. 启动服务 ----------
Write-Step 6 "启动后端与前端服务..."
Write-Host ""
Write-Host "       后端: 启动中（端口 8000）..."
$backendProc = Start-Process -FilePath "python" -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000","--log-level","warning" -PassThru -WindowStyle Minimized
Write-Host "       前端: 启动中（端口 8501）..."
$frontendProc = Start-Process -FilePath "python" -ArgumentList "-m","streamlit","run","app_frontend.py","--server.headless=true","--browser.gatherUsageStats=false" -PassThru -WindowStyle Minimized

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  服务正在后台启动，首次约需 10-15 秒..." -ForegroundColor Cyan
Write-Host "  浏览器将自动打开，如未自动打开请手动访问:" -ForegroundColor Cyan
Write-Host ""
Write-Host "    前端页面:  http://localhost:8501" -ForegroundColor Yellow
Write-Host "    API 文档:  http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  关闭本窗口将同时退出整个系统（后端+前端）" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 等待服务就绪后打开浏览器
Start-Sleep -Seconds 8
Start-Process "http://localhost:8501"
Write-Host "[完成] 浏览器已打开" -ForegroundColor Green
Write-Host ""

# 等待用户退出
Write-Host "按任意键退出系统..." -ForegroundColor Yellow
[void][System.Console]::ReadKey($true)

# ---------- 退出清理：用 PID 精准结束 ----------
Write-Host ""
Write-Host "正在停止服务..." -ForegroundColor Cyan
foreach ($p in @($backendProc, $frontendProc)) {
    if ($p -and -not $p.HasExited) {
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    }
}
# 同时结束子进程（python 启动的子进程）
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'uvicorn|streamlit' } | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Write-Host "已退出，再见！" -ForegroundColor Green
Start-Sleep -Seconds 2
