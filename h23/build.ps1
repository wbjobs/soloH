param(
    [switch]$Test,
    [switch]$Clean,
    [switch]$Run
)

$BinaryName = "randomness-tester.exe"

if ($Clean) {
    Write-Host "Cleaning..."
    if (Test-Path $BinaryName) {
        Remove-Item $BinaryName -Force
    }
    Get-ChildItem -Filter *.json -ErrorAction SilentlyContinue | Remove-Item -Force
    Get-ChildItem -Filter *.txt -ErrorAction SilentlyContinue | Remove-Item -Force
    Write-Host "Clean complete."
    return
}

Write-Host "Building randomness-tester..."
go build -o $BinaryName ./cmd/randomness-tester

if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "Build successful: $BinaryName"

if ($Test) {
    Write-Host "Running tests..."
    go test -v ./...
}

if ($Run) {
    Write-Host "Listing available tests..."
    .\$BinaryName -list-tests
}
