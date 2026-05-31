param(
    [switch]$WithHDF5
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

Write-Host "=== Boolean Network Analyzer Build Script ===" -ForegroundColor Cyan

$mingwDir = Join-Path $PSScriptRoot "mingw64"
$gppPath = Join-Path $mingwDir "bin\g++.exe"

if (-not (Test-Path $gppPath)) {
    Write-Host "MinGW not found, downloading..." -ForegroundColor Yellow
    
    $mirrors = @(
        "https://mirrors.tuna.tsinghua.edu.cn/github-release/niXman/mingw-builds-binaries/14.2.0-rt_v12-rev0/x86_64-14.2.0-release-posix-seh-msvcrt-rt_v12-rev0.7z",
        "https://mirrors.aliyun.com/github-release/niXman/mingw-builds-binaries/14.2.0-rt_v12-rev0/x86_64-14.2.0-release-posix-seh-msvcrt-rt_v12-rev0.7z",
        "https://github.com/niXman/mingw-builds-binaries/releases/download/14.2.0-rt_v12-rev0/x86_64-14.2.0-release-posix-seh-msvcrt-rt_v12-rev0.7z"
    )
    
    $downloaded = $false
    foreach ($mirror in $mirrors) {
        try {
            Write-Host "Trying mirror: $mirror"
            $archivePath = Join-Path $PSScriptRoot "mingw.7z"
            Invoke-WebRequest -Uri $mirror -OutFile $archivePath -UseBasicParsing -TimeoutSec 300
            if (Test-Path $archivePath -and (Get-Item $archivePath).Length -gt 10MB) {
                $downloaded = $true
                Write-Host "Download completed successfully!" -ForegroundColor Green
                break
            }
        }
        catch {
            Write-Host "Mirror failed: $_" -ForegroundColor Red
            continue
        }
    }
    
    if (-not $downloaded) {
        Write-Host "ERROR: Failed to download MinGW from any mirror." -ForegroundColor Red
        Write-Host "Please install MinGW-w64 manually and add it to PATH." -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "Extracting MinGW..." -ForegroundColor Yellow
    $sevenZip = Get-Command 7z.exe -ErrorAction SilentlyContinue
    if ($sevenZip) {
        & 7z.exe x -y "mingw.7z" | Out-Null
    }
    else {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        try {
            [System.IO.Compression.ZipFile]::ExtractToDirectory("mingw.7z", $PSScriptRoot)
        }
        catch {
            Write-Host "ERROR: Cannot extract .7z file. Please install 7-Zip." -ForegroundColor Red
            exit 1
        }
    }
    
    Remove-Item "mingw.7z" -Force
    
    if (-not (Test-Path $gppPath)) {
        Write-Host "ERROR: g++.exe not found after extraction." -ForegroundColor Red
        exit 1
    }
}

$env:PATH = "$mingwDir\bin;$env:PATH"

Write-Host "Using compiler: $gppPath" -ForegroundColor Green
& g++ --version | Select-Object -First 1

Write-Host ""
Write-Host "Building project..." -ForegroundColor Yellow

$cxxFlags = @("-std=c++17", "-Wall", "-Wextra", "-O2", "-Iinclude")
if ($WithHDF5) {
    $cxxFlags += "-DBN_WITH_HDF5"
    $ldFlags = @("-lhdf5_cpp", "-lhdf5")
}
else {
    $ldFlags = @()
}

$sources = @("src\boolean_network.cpp", "src\main.cpp")
$target = "bn_analyzer.exe"

$compileArgs = $cxxFlags + $sources + @("-o", $target) + $ldFlags

Write-Host "g++ $($compileArgs -join ' ')"
& g++ @compileArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Build failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Build successful! Output: $target" -ForegroundColor Green
Write-Host ""
Write-Host "To run tests:" -ForegroundColor Cyan
Write-Host "  .\$target examples\simple_network.txt" -ForegroundColor Gray
Write-Host "  .\$target -s 200 -b 1000 examples\cycle_network.txt" -ForegroundColor Gray
Write-Host "  .\$target -s 500 -b 2000 -p 1 -l 5000 examples\cell_cycle.txt" -ForegroundColor Gray

exit 0
