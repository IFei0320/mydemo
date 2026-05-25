@echo off
setlocal

echo ========================================
echo   Django Development Server
echo ========================================

cd /d D:\ass\mydemo
if errorlevel 1 (
    echo [ERROR] Cannot find project directory
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
if "%VIRTUAL_ENV%"=="" (
    echo [ERROR] Failed to activate venv
    pause
    exit /b 1
)

echo [INFO] venv: %VIRTUAL_ENV%
echo [INFO] Installing dependencies...
venv\Scripts\python.exe -m pip install cryptography pymysql --quiet

venv\Scripts\python.exe -c "import cryptography; import pymysql"
if errorlevel 1 (
    echo [ERROR] cryptography or pymysql missing
    pause
    exit /b 1
)

echo [INFO] Starting http://127.0.0.1:8000/
echo ========================================
python manage.py runserver
pause
