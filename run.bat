@echo off
echo ========================================
echo   Starting Django Development Server
echo ========================================

:: 切换到项目目录
cd /d D:\ass\mydemo

:: 激活虚拟环境
call venv\Scripts\activate.bat

:: 检查虚拟环境是否激活成功
if "%VIRTUAL_ENV%"=="" (
    echo [ERROR] Failed to activate virtual environment!
    pause
    exit /b 1
)

echo [INFO] Virtual environment activated: %VIRTUAL_ENV%
echo [INFO] Checking dependencies...

:: 检查关键依赖
python -c "import cryptography" 2>nul
if errorlevel 1 (
    echo [WARNING] Installing missing dependency: cryptography
    pip install cryptography
)

:: 运行 Django 服务器
echo [INFO] Starting server at http://127.0.0.1:8000/
python manage.py runserver

pause
