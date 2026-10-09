@echo off
rem Install yf terminal command (needs Python 3)
chcp 65001 >nul
where python >nul 2>nul
if errorlevel 1 (
    echo [yf] Python 3 not found. Install it first.
    pause
    exit /b 1
)
python "%~dp0scripts\install_yf.py"
pause