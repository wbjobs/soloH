@echo off
chcp 65001
title 古籍文字识别系统 - 全套服务

echo ========================================
echo  古籍文字识别系统 - 全套服务启动
echo ========================================
echo.

cd /d "%~dp0"

echo [*] 正在启动后端服务...
start "后端服务" cmd /k call start-backend.bat

timeout /t 3 /nobreak >nul

echo [*] 正在启动前端服务...
start "前端服务" cmd /k call start-frontend.bat

echo.
echo ========================================
echo  所有服务已启动！
echo  前端: http://localhost:5173
echo  后端: http://localhost:5000
echo ========================================
echo.
echo 请关闭此窗口前先关闭各服务窗口
pause
