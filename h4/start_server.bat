@echo off
echo Starting local web server on port 8080...
echo.
echo Open your browser and navigate to: http://localhost:8080
echo.
echo Press Ctrl+C to stop the server.
echo.

python -m http.server 8080

if %ERRORLEVEL% NEQ 0 (
  echo Python not found, trying Node.js...
  npx http-server -p 8080
)

pause
