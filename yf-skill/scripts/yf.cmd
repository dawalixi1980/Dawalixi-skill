@echo off
rem yf launcher: runs yf.py in the same folder
setlocal
chcp 65001 >nul
where python >nul 2>nul
if not errorlevel 1 goto run
echo [yf] Python not found. Install Python 3 first.
exit /b 1
:run
python "%~dp0yf.py" %*
exit /b %errorlevel%