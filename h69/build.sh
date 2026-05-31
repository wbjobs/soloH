#!/bin/bash

echo "========================================"
echo "Harmonic Balance Solver - Build Script"
echo "========================================"
echo ""

COMPILER=""
if command -v g++ &> /dev/null; then
    COMPILER="g++"
elif command -v clang++ &> /dev/null; then
    COMPILER="clang++"
else
    echo "ERROR: No C++ compiler found. Please install g++ or clang++."
    exit 1
fi

echo "Using compiler: $COMPILER"
echo ""

mkdir -p build
cd build

echo "Compiling source files..."
$COMPILER -std=c++17 -O3 -I../include \
    ../src/fft.cpp \
    ../src/matrix.cpp \
    ../src/nonlinear.cpp \
    ../src/circuit.cpp \
    ../src/hbsolver.cpp \
    ../src/analysis.cpp \
    ../src/output.cpp \
    ../src/main.cpp \
    -o hbsolver

if [ $? -ne 0 ]; then
    echo ""
    echo "Compilation failed!"
    cd ..
    exit 1
fi

echo ""
echo "========================================"
echo "Build successful!"
echo "Executable: build/hbsolver"
echo "========================================"
echo ""
echo "Run examples:"
echo "  ./hbsolver --help"
echo "  ./hbsolver --model diode --tone 1e9,0.1 --plot-spectrum"
echo "  ./hbsolver --model fet --two-tone 1e9,1.001e9,0.1,0.1 --harmonics 7"
echo ""
cd ..
