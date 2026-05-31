@echo off
echo ========================================
echo Harmonic Balance Solver - Build Script
echo ========================================
echo.

where cl.exe >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Microsoft Visual C++ compiler (cl.exe) not found.
    echo Please run this script from Visual Studio Developer Command Prompt.
    echo Or install Visual Studio with C++ support.
    echo.
    echo Alternative: Using CMake with MinGW:
    echo   cmake -G "MinGW Makefiles" -B build
    echo   cmake --build build
    echo.
    pause
    exit /b 1
)

echo Using MSVC compiler...
echo.

if not exist build mkdir build
cd build

echo Compiling source files...
cl.exe /std:c++17 /EHsc /O2 /I../include ^
    ../src/fft.cpp ^
    ../src/matrix.cpp ^
    ../src/nonlinear.cpp ^
    ../src/circuit.cpp ^
    ../src/hbsolver.cpp ^
    ../src/analysis.cpp ^
    ../src/output.cpp ^
    ../src/main.cpp ^
    /Fe:hbsolver.exe

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Compilation failed!
    cd ..
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build successful!
echo Executable: build\hbsolver.exe
echo ========================================
echo.
echo Run examples:
echo   hbsolver.exe --help
echo   hbsolver.exe --model diode --tone 1e9,0.1 --plot-spectrum
echo   hbsolver.exe --model fet --two-tone 1e9,1.001e9,0.1,0.1 --harmonics 7
echo.
cd ..
pause
