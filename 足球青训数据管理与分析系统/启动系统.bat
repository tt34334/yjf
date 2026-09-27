@echo off
cd /d "%~dp0"
title Football Academy System

REM Check Python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo Please install Python 3.10+ and add it to PATH.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Create venv if not exists
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Run launcher with venv python
".venv\Scripts\python.exe" launcher.py
if errorlevel 1 pause
