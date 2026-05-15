@echo off
cd /d D:\ass\mydemo

REM 检查虚拟环境是否存在
if not exist venv\Scripts\activate.bat (
    echo 正在使用 Python 3.12 创建虚拟环境...
    py -3.12 -m venv venv
    if errorlevel 1 (
        echo ❌ 创建失败！请确认 Python 3.12 已安装
        pause
        exit /b 1
    )
)

echo 激活虚拟环境...
call venv\Scripts\activate

echo 验证 Python 版本...
python --version

echo.
echo 启动 Django 服务器...
echo ========================================
python manage.py runserver

pause
