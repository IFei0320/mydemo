@echo off
setlocal

echo ========================================
echo   Django Development Server
echo ========================================

cd /d "%~dp0"
if errorlevel 1 (
    echo [ERROR] Cannot find project directory
    pause
    exit /b 1
)

call ..\.venv\Scripts\activate.bat
if "%VIRTUAL_ENV%"=="" (
    echo [ERROR] Failed to activate venv
    pause
    exit /b 1
)

echo [INFO] venv: %VIRTUAL_ENV%
echo [INFO] Starting http://127.0.0.1:8000/
echo ========================================
python manage.py runserver
pause
