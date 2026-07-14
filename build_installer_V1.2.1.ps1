# build_installer_V1.2.1.ps1
# Automates the entire QuantileCull V1.2.1 Desktop App compilation and installer packaging.

$ErrorActionPreference = "Stop"

Write-Host "=== STARTING QUANTILECULL V1.2.1 BUILD PROCESS ===" -ForegroundColor Cyan

# 1. Locate Inno Setup Compiler (ISCC.exe)
$isccPaths = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)

$isccPath = $null
foreach ($path in $isccPaths) {
    if (Test-Path $path) {
        $isccPath = $path
        break
    }
}

if (-not $isccPath) {
    Write-Error "Inno Setup Compiler (ISCC.exe) not found! Please install Inno Setup 6."
    exit 1
}
Write-Host "[OK] Found Inno Setup Compiler at: $isccPath" -ForegroundColor Green

# 2. Run PyInstaller
Write-Host "Compiling standalone Python binary (QuantileCull_V1.2.1.spec)..." -ForegroundColor Yellow
$pyinstallerPath = "E:\Antigravity Projects\Photo Cleaner App\.venv\Scripts\pyinstaller.exe"
if (-not (Test-Path $pyinstallerPath)) {
    Write-Error "PyInstaller not found in virtual environment!"
    exit 1
}

& $pyinstallerPath QuantileCull_V1.2.1.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller compilation failed!"
    exit 1
}
Write-Host "[OK] PyInstaller compilation completed successfully." -ForegroundColor Green

# 3. Run Inno Setup Compiler
Write-Host "Compiling setup installer package (setup_V1.2.1.iss)..." -ForegroundColor Yellow
& $isccPath setup_V1.2.1.iss
if ($LASTEXITCODE -ne 0) {
    Write-Host "Inno Setup compilation failed!"
    exit 1
}

$outputExe = "E:\Antigravity Projects\Photo Cleaner App\dist\QuantileCull_1.2.1_Setup.exe"
if (Test-Path $outputExe) {
    Write-Host "[SUCCESS] V1.2.1 Setup Installer successfully compiled at: $outputExe" -ForegroundColor Green
} else {
    Write-Error "Compilation finished but installer executable was not found!"
}
