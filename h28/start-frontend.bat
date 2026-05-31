@echo off
chcp 65001
echo ========================================
echo  古籍文字识别系统 - 前端启动脚本
echo ========================================
echo.

cd /d "%~dp0frontend"

echo [1/3] 检查Node.js环境...
node --version
if %errorlevel% neq 0 (
    echo 错误: 未找到Node.js，请先安装Node.js 18+
    pause
    exit /b 1
)

echo.
echo [2/3] 检查依赖包...
if not exist "node_modules" (
    echo 正在安装依赖包...
    npm install
)

echo.
echo [3/3] 启动Vite开发服务器...
echo 服务地址: http://localhost:5173
echo.
echo 按 Ctrl+C 停止服务
echo ========================================
echo.

npm run dev
