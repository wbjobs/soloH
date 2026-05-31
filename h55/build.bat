@echo off
REM Build script for MotifDiscovery tool

echo Building Motif Discovery Tool...
echo.

where g++ >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: g++ not found. Please install MinGW or GCC.
    echo.
    echo You can install MinGW using winget:
    echo   winget install BrechtSanders.WinLibs.POSIX.UCRT
    echo.
    echo After installation, restart your terminal and run this script again.
    exit /b 1
)

echo Using compiler:
g++ --version
echo.

if not exist build mkdir build

echo Compiling with OpenMP...
g++ -std=c++17 -O2 -Wall -Wextra -fopenmp -Iinclude src/main.cpp -o build/motif_discovery.exe

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Build successful!
    echo Executable: build\motif_discovery.exe
    echo.
    echo To run:
    echo   build\motif_discovery.exe -i example.fasta -w 8
) else (
    echo.
    echo Build failed.
    exit /b 1
)
