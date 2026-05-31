#!/bin/bash
# Build script for MotifDiscovery tool (Linux/macOS)

echo "Building Motif Discovery Tool..."
echo

if ! command -v g++ &> /dev/null; then
    echo "Error: g++ not found. Please install GCC."
    exit 1
fi

echo "Using compiler:"
g++ --version
echo

mkdir -p build

echo "Compiling..."
g++ -std=c++17 -O2 -Wall -Wextra -Iinclude src/main.cpp -o build/motif_discovery -lpthread

if [ $? -eq 0 ]; then
    echo
    echo "Build successful!"
    echo "Executable: build/motif_discovery"
    echo
    echo "To run:"
    echo "  ./build/motif_discovery -i example.fasta -w 8"
else
    echo
    echo "Build failed."
    exit 1
fi
