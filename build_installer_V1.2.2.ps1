# build_installer_V1.2.2.ps1
# Automates the entire QuantileCull V1.2.2 Desktop App compilation and installer packaging.

$ErrorActionPreference = "Stop"

Write-Host "=== STARTING QUANTILECULL V1.2.2 BUILD PROCESS ===" -ForegroundColor Cyan

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

# 2. Move static folder executables to a temporary location to prevent recursive packaging
$tempExeDir = "E:\Antigravity Projects\Photo Cleaner App\scratch\temp_build_exes"
if (-not (Test-Path $tempExeDir)) {
    New-Item -ItemType Directory -Path $tempExeDir -Force | Out-Null
}

$staticExeFiles = Get-ChildItem -Path "E:\Antigravity Projects\Photo Cleaner App\static\*.exe"
if ($staticExeFiles) {
    Write-Host "Temporarily moving static setup files out of static folder to avoid recursive bundling..." -ForegroundColor Yellow
    foreach ($file in $staticExeFiles) {
        Move-Item -Path $file.FullName -Destination (Join-Path $tempExeDir $file.Name) -Force
    }
}

# 3. Run PyInstaller
Write-Host "Compiling standalone Python binary (QuantileCull_V1.2.2.spec)..." -ForegroundColor Yellow
$pyinstallerPath = "E:\Antigravity Projects\Photo Cleaner App\.venv\Scripts\pyinstaller.exe"
if (-not (Test-Path $pyinstallerPath)) {
    Write-Error "PyInstaller not found in virtual environment!"
    exit 1
}

& $pyinstallerPath QuantileCull_V1.2.2.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) {
    # Restore even if PyInstaller fails
    if (Test-Path $tempExeDir) {
        Get-ChildItem -Path (Join-Path $tempExeDir "*.exe") | ForEach-Object { Move-Item -Path $_.FullName -Destination "E:\Antigravity Projects\Photo Cleaner App\static\" -Force }
        Remove-Item $tempExeDir -Recurse -Force
    }
    Write-Error "PyInstaller compilation failed!"
    exit 1
}
Write-Host "[OK] PyInstaller compilation completed successfully." -ForegroundColor Green

# 4. Run Inno Setup Compiler
Write-Host "Compiling setup installer package (setup_V1.2.2.iss)..." -ForegroundColor Yellow
& $isccPath setup_V1.2.2.iss
if ($LASTEXITCODE -ne 0) {
    # Restore even if Inno Setup fails
    if (Test-Path $tempExeDir) {
        Get-ChildItem -Path (Join-Path $tempExeDir "*.exe") | ForEach-Object { Move-Item -Path $_.FullName -Destination "E:\Antigravity Projects\Photo Cleaner App\static\" -Force }
        Remove-Item $tempExeDir -Recurse -Force
    }
    Write-Host "Inno Setup compilation failed!"
    exit 1
}

# 5. Restore original static files and deploy the newly built installer
if (Test-Path $tempExeDir) {
    $tempExeFiles = Get-ChildItem -Path (Join-Path $tempExeDir "*.exe")
    if ($tempExeFiles) {
        Write-Host "Restoring static setup files..." -ForegroundColor Yellow
        foreach ($file in $tempExeFiles) {
            Move-Item -Path $file.FullName -Destination "E:\Antigravity Projects\Photo Cleaner App\static\" -Force
        }
    }
    Remove-Item $tempExeDir -Recurse -Force
}

$outputExe = "E:\Antigravity Projects\Photo Cleaner App\dist\QuantileCull_1.2.2_Setup.exe"
if (Test-Path $outputExe) {
    Write-Host "[SUCCESS] V1.2.2 Setup Installer successfully compiled at: $outputExe" -ForegroundColor Green
    
    # Copy newly built installer to static/ as V1.2.2 download
    Copy-Item $outputExe "E:\Antigravity Projects\Photo Cleaner App\static\QuantileCull_1.2.2_Setup.exe" -Force
    
    # Also replace V1.2.1 download immediately as requested
    Copy-Item $outputExe "E:\Antigravity Projects\Photo Cleaner App\static\QuantileCull_1.2.1_Setup.exe" -Force
    Write-Host "[OK] Copied installer to static folder for web serving (updating both 1.2.2 and 1.2.1 endpoints)." -ForegroundColor Green
} else {
    Write-Error "Compilation finished but installer executable was not found!"
}
