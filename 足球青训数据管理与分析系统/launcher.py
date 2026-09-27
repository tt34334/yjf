# -*- coding: utf-8 -*-
"""
足球青训数据管理系统 - 一键启动器
双击"启动系统.bat"会调用此脚本
"""
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).parent
os.chdir(ROOT)

# 颜色输出（Windows 10+ 支持 ANSI）
os.system("")  # 启用 ANSI 转义


def cprint(msg, color=""):
    colors = {
        "green": "\033[92m", "red": "\033[91m", "yellow": "\033[93m",
        "cyan": "\033[96m", "bold": "\033[1m", "end": "\033[0m",
    }
    c = colors.get(color, "")
    print(f"{c}{msg}{colors['end']}")


def step(num, msg):
    cprint(f"[{num}/6] {msg}", "green")


def fail(msg):
    cprint(f"[错误] {msg}", "red")
    input("按回车键退出...")
    sys.exit(1)


def warn(msg):
    cprint(f"[警告] {msg}", "yellow")


cprint("=" * 60, "cyan")
cprint("   足球青训数据管理系统  -  一键启动器", "cyan")
cprint("=" * 60, "cyan")
print()

# ---------- 1. Python 版本 ----------
cprint(f"[1/6] 检测到 Python {sys.version.split()[0]}", "green")

# ---------- 2. 虚拟环境 ----------
venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
if not venv_python.exists():
    step(2, "创建虚拟环境...")
    ret = subprocess.run([sys.executable, "-m", "venv", ".venv"])
    if ret.returncode != 0 or not venv_python.exists():
        fail("虚拟环境创建失败")
else:
    step(2, "虚拟环境已存在")

# 用 venv 的 python 执行后续命令
PY = str(venv_python)
PIP = [PY, "-m", "pip"]

# ---------- 3. 依赖检查与安装 ----------
def check_deps():
    try:
        r = subprocess.run(
            [PY, "-c", "import fastapi, streamlit, plotly, pandas"],
            capture_output=True, timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False

if not check_deps():
    step(3, "首次启动，安装依赖中（约1-3分钟，请耐心等待）...")
    subprocess.run(PIP + ["install", "--upgrade", "pip", "-q"])
    r = subprocess.run(PIP + ["install", "-r", "requirements.txt", "-q"])
    if r.returncode != 0:
        warn("官方源安装失败，尝试国内镜像源...")
        r2 = subprocess.run(PIP + [
            "install", "-r", "requirements.txt",
            "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
        ])
        if r2.returncode != 0:
            fail("依赖安装失败，请检查网络")
    print("       依赖安装完成")
else:
    step(3, "依赖已就绪")

# ---------- 4. 配置文件 ----------
env_file = ROOT / ".env"
if not env_file.exists():
    step(4, "生成默认配置（使用 SQLite，无需安装 MySQL）...")
    env_file.write_text(
        "DATABASE_URL=sqlite:///./academy.db\n"
        "REDIS_URL=redis://localhost:6379/0\n"
        "APP_NAME=足球青训数据管理 API\n"
        "DEBUG=true\n"
        "EXPORT_DIR=./exports\n",
        encoding="utf-8",
    )
    exports_dir = ROOT / "exports"
    exports_dir.mkdir(exist_ok=True)
else:
    step(4, "配置文件 .env 已存在")

# ---------- 5. 数据库初始化 ----------
step(5, "检查数据库...")
db_file = ROOT / "academy.db"
need_seed = False
if not db_file.exists():
    print("       首次启动，初始化数据库和种子数据...")
    need_seed = True
else:
    try:
        r = subprocess.run(
            [PY, "-c",
             "import sqlite3; con=sqlite3.connect('academy.db'); "
             "cur=con.cursor(); cur.execute('SELECT count(*) FROM players'); "
             "print(cur.fetchone()[0])"],
            capture_output=True, timeout=10,
        )
        out = r.stdout.decode().strip() if r.stdout else "0"
        if out and int(out) > 0:
            print("       数据库已就绪")
        else:
            print("       数据库无数据，重新生成种子数据...")
            need_seed = True
    except Exception:
        print("       数据库检查异常，尝试重新初始化...")
        need_seed = True

if need_seed:
    r = subprocess.run([PY, "-m", "app.seed"])
    if r.returncode != 0:
        warn("种子数据初始化异常，但服务仍会尝试启动")

# ---------- 6. 启动服务 ----------
step(6, "启动后端与前端服务...")
# 用 STARTUPINFO 隐藏控制台窗口，但保留 stdout（CREATE_NO_WINDOW 会让 streamlit 崩溃）
si = subprocess.STARTUPINFO()
si.dwFlags = subprocess.STARTF_USESHOWWINDOW
si.wShowWindow = 0  # SW_HIDE

print()
print("       后端: 启动中（端口 8000）...")
backend = subprocess.Popen(
    [PY, "-m", "uvicorn", "app.main:app",
     "--host", "127.0.0.1", "--port", "8000", "--log-level", "warning"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    startupinfo=si,
)
print("       前端: 启动中（端口 8501）...")
frontend = subprocess.Popen(
    [PY, "-m", "streamlit", "run", "app_frontend.py",
     "--server.headless=true", "--browser.gatherUsageStats=false"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    startupinfo=si,
)

print()
cprint("=" * 60, "cyan")
cprint("  服务正在后台启动，首次约需 10-15 秒...", "cyan")
cprint("  浏览器将自动打开，如未自动打开请手动访问:", "cyan")
print()
cprint("    前端页面:  http://localhost:8501", "yellow")
cprint("    API 文档:  http://localhost:8000/docs", "yellow")
cprint("=" * 60, "cyan")
print()
cprint("  关闭本窗口将同时退出整个系统（后端+前端）", "yellow")
cprint("=" * 60, "cyan")
print()

# 等待服务就绪后打开浏览器（轮询检查，最多 30 秒）
import urllib.request

def wait_for_port(url, name, max_wait=30):
    """轮询检查服务是否就绪"""
    for i in range(max_wait):
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            if i == 0:
                print(f"       等待{name}就绪...", end="", flush=True)
            else:
                print(".", end="", flush=True)
            time.sleep(1)
    print()
    return False

print()
be_ok = wait_for_port("http://localhost:8000/api/statistics/team", "后端", 15)
print()
fe_ok = wait_for_port("http://localhost:8501", "前端", 30)
print()

if fe_ok:
    webbrowser.open("http://localhost:8501")
    cprint("[完成] 浏览器已打开", "green")
elif be_ok:
    # 前端没就绪但后端 OK，可能是 streamlit 首次编译慢
    warn("前端启动较慢，请稍后手动访问 http://localhost:8501")
else:
    warn("服务启动可能失败，请稍后手动访问 http://localhost:8501")
print()

# 等待用户退出
try:
    input("按回车键退出系统...")
except (EOFError, KeyboardInterrupt):
    pass  # 非交互环境（如双击被重定向），直接进入清理

# ---------- 退出清理 ----------
print()
cprint("正在停止服务...", "cyan")
for proc in [backend, frontend]:
    if proc.poll() is None:  # 还在运行
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

# 额外清理：杀掉残留的 uvicorn/streamlit 子进程
try:
    subprocess.run(
        ["taskkill", "/im", "python.exe", "/fi",
         "WINDOWTITLE eq 后端_足球*", "/f"],
        capture_output=True,
    )
except Exception:
    pass

cprint("已退出，再见！", "green")
time.sleep(1.5)
