@echo off
chcp 65001
echo ========================================
echo  古籍文字识别系统 - 后端启动脚本
echo ========================================
echo.

cd /d "%~dp0backend"

echo [1/3] 检查Python环境...
python --version
if %errorlevel% neq 0 (
    echo 错误: 未找到Python，请先安装Python 3.10+
    pause
    exit /b 1
)

echo.
echo [2/3] 检查依赖包...
python -c "import flask" 2>nul
if %errorlevel% neq 0 (
    echo 正在安装依赖包...
    pip install -r requirements.txt
)

echo.
echo [3/3] 启动Flask服务...
echo 服务地址: http://localhost:5000
echo API文档: http://localhost:5000/api/health
echo.
echo 按 Ctrl+C 停止服务
echo ========================================
echo.

python run.py
