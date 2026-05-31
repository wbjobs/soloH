@echo off
echo ========================================
echo BB84 Simulator - Windows Build Script
echo ========================================
echo.

REM Set up Visual Studio environment if not already set
if not defined VSINSTALLDIR (
    if exist "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" (
        echo Setting up Visual Studio 2022 environment...
        call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
    ) else if exist "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat" (
        echo Setting up Visual Studio 2022 Professional environment...
        call "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat"
    ) else if exist "C:\Program Files\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat" (
        echo Setting up Visual Studio 2019 environment...
        call "C:\Program Files\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"
    ) else (
        echo WARNING: Visual Studio not found in standard locations.
        echo Please run this script from a Visual Studio Developer Command Prompt.
    )
)

echo.
echo Creating build directory...
if not exist build mkdir build
cd build

echo.
echo Building with MSVC...
cl.exe /std:c++17 /EHsc /O2 /W4 /I..\include ^
    ..\src\utils.cpp ^
    ..\src\quantum.cpp ^
    ..\src\alice.cpp ^
    ..\src\bob.cpp ^
    ..\src\eve.cpp ^
    ..\src\cascade.cpp ^
    ..\src\privacy_amplification.cpp ^
    ..\src\bb84.cpp ^
    ..\src\stats.cpp ^
    ..\src\main.cpp ^
    /Fe:bb84_simulator.exe

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo Build successful!
    echo Executable: build\bb84_simulator.exe
    echo ========================================
) else (
    echo.
    echo ========================================
    echo Build failed with error code %ERRORLEVEL%
    echo ========================================
    exit /b %ERRORLEVEL%
)

cd ..
