@echo off
echo Building WASM module...

if not exist "wasm" mkdir wasm

emcc cpp/magnetic_field.cpp ^
  -o wasm/magnetic_field.js ^
  -s WASM=1 ^
  -s ALLOW_MEMORY_GROWTH=1 ^
  -s MODULARIZE=1 ^
  -s EXPORT_ES6=0 ^
  -s USE_ES6_IMPORT_META=0 ^
  -s EXPORT_NAME="Module" ^
  -s EXPORTED_RUNTIME_METHODS=["ccall","cwrap"] ^
  -s BINDINGS=1 ^
  -std=c++17 ^
  -O3 ^
  --bind

if %ERRORLEVEL% EQU 0 (
  echo WASM build successful!
  copy /Y wasm\magnetic_field.js js\magnetic_wasm.js
  echo Copied JS wrapper to js/ directory
) else (
  echo WASM build failed. Using JS fallback.
)

pause
