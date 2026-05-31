@echo off
setlocal

echo === Boolean Network Analyzer Build Script ===
echo.

where g++ >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: g++ not found in PATH.
    echo Please install MinGW-w64 and add it to PATH, or run:
    echo   powershell -ExecutionPolicy Bypass -File build.ps1
    echo.
    exit /b 1
)

echo Using compiler:
g++ --version | head -1
echo.

set CXXFLAGS=-std=c++17 -Wall -Wextra -O2 -Iinclude
set LDFLAGS=
set SOURCES=src\boolean_network.cpp src\main.cpp
set TARGET=bn_analyzer.exe

echo Building: %TARGET%
echo g++ %CXXFLAGS% %SOURCES% -o %TARGET% %LDFLAGS%
g++ %CXXFLAGS% %SOURCES% -o %TARGET% %LDFLAGS%

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Build failed with exit code %errorlevel%
    exit /b 1
)

echo.
echo Build successful! Output: %TARGET%
echo.
echo Usage examples:
echo   %TARGET% examples\simple_network.txt
echo   %TARGET% -s 200 -b 1000 examples\cycle_network.txt
echo   %TARGET% -s 500 -b 2000 -p 1 -l 5000 -o landscape.txt examples\cell_cycle.txt
echo.

endlocal
