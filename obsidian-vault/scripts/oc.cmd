@echo off
rem oc: open current folder (or given folder) in OpenCode desktop
setlocal
chcp 65001 >nul
where python >nul 2>nul
if not errorlevel 1 goto run
echo [oc] Python not found. Install Python 3 first.
exit /b 1
:run
python "%~dp0oc.py" %*
exit /b %errorlevel%