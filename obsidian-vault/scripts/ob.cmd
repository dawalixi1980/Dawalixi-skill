@echo off
rem ob: open current folder (or given folder) in Obsidian as a vault
setlocal
chcp 65001 >nul
where python >nul 2>nul
if not errorlevel 1 goto run
echo [ob] Python not found. Install Python 3 first.
exit /b 1
:run
python "%~dp0ob.py" %*
exit /b %errorlevel%