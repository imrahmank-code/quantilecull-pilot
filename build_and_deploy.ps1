# build_and_deploy.ps1
# Automates the clean, two-source desktop app distribution pipeline for QuantileCull V1.2.2.

$ErrorActionPreference = "Stop"

Write-Host "=== STARTING QUANTILECULL V1.2.2 DEPLOYMENT PIPELINE ===" -ForegroundColor Cyan

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

# --- STEP 1: CLEAN PREVIOUS ARTIFACTS ---
Write-Host "--- STEP 1: CLEANING PREVIOUS ARTIFACTS ---" -ForegroundColor Yellow
if (Test-Path "E:\Antigravity Projects\Photo Cleaner App\dist") {
    Write-Host "Clearing dist/ directory..." -ForegroundColor Gray
    Remove-Item "E:\Antigravity Projects\Photo Cleaner App\dist\*" -Force -Recurse -ErrorAction SilentlyContinue
} else {
    New-Item -ItemType Directory -Path "E:\Antigravity Projects\Photo Cleaner App\dist" -Force | Out-Null
}

Write-Host "Clearing setup executables from static/ directory..." -ForegroundColor Gray
Get-ChildItem -Path "E:\Antigravity Projects\Photo Cleaner App\static\*.exe" -ErrorAction SilentlyContinue | Remove-Item -Force
Write-Host "[OK] Artifacts cleared successfully." -ForegroundColor Green

# --- STEP 2: BUILD EXECUTABLE ---
Write-Host "--- STEP 2: RUNNING PYINSTALLER COMPILATION ---" -ForegroundColor Yellow
$pyinstallerPath = "E:\Antigravity Projects\Photo Cleaner App\.venv\Scripts\pyinstaller.exe"
if (-not (Test-Path $pyinstallerPath)) {
    Write-Error "PyInstaller not found in virtual environment!"
    exit 1
}

& $pyinstallerPath QuantileCull_V1.2.2.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller compilation failed!"
    exit 1
}
Write-Host "[OK] Standalone executable compiled at dist/QuantileCull_1.2.2.exe" -ForegroundColor Green

# --- STEP 3: BUILD INSTALLER WIZARD ---
Write-Host "--- STEP 3: RUNNING INNO SETUP COMPILER ---" -ForegroundColor Yellow
& $isccPath setup_V1.2.2.iss
if ($LASTEXITCODE -ne 0) {
    Write-Error "Inno Setup compiler failed!"
    exit 1
}
Write-Host "[OK] Installer wizard compiled at dist/QuantileCull_1.2.2_Setup.exe" -ForegroundColor Green

# --- STEP 4: PROCESS & CLEANUP DIST ---
Write-Host "--- STEP 4: RETAINING ONLY INSTALLER IN DIST/ ---" -ForegroundColor Yellow
$rawExe = "E:\Antigravity Projects\Photo Cleaner App\dist\QuantileCull_1.2.2.exe"
if (Test-Path $rawExe) {
    Remove-Item $rawExe -Force
    Write-Host "[OK] Deleted raw intermediate executable from dist/." -ForegroundColor Green
} else {
    Write-Warning "Raw executable not found to delete!"
}

# --- STEP 5: PUBLIC STATIC DEPLOYMENT ---
Write-Host "--- STEP 5: DEPLOYING UNVERSIONED INSTALLER TO STATIC/ ---" -ForegroundColor Yellow
$compiledSetup = "E:\Antigravity Projects\Photo Cleaner App\dist\QuantileCull_1.2.2_Setup.exe"
$staticTarget = "E:\Antigravity Projects\Photo Cleaner App\static\QuantileCull_Setup.exe"

if (Test-Path $compiledSetup) {
    Copy-Item -Path $compiledSetup -Destination $staticTarget -Force
    Write-Host "[OK] Copied and renamed installer to $staticTarget" -ForegroundColor Green
} else {
    Write-Error "Compiled setup installer not found!"
    exit 1
}

# --- STEP 6: VERIFICATION ---
Write-Host "--- STEP 6: VERIFYING BUILD ENVIRONMENT ---" -ForegroundColor Yellow
$distContents = Get-ChildItem -Path "E:\Antigravity Projects\Photo Cleaner App\dist" -File
$staticContents = Get-ChildItem -Path "E:\Antigravity Projects\Photo Cleaner App\static" -File -Filter "*.exe"

Write-Host "`n=======================================================" -ForegroundColor Cyan
Write-Host "             DEPLOYMENT PIPELINE SUCCESS LOG            " -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "FINAL 'dist/' CONTENTS:" -ForegroundColor Green
$distContents | ForEach-Object { Write-Host "  - $($_.Name) ($([math]::round($_.Length / 1MB, 2)) MB)" }

Write-Host "`nFINAL 'static/' EXECUTABLES:" -ForegroundColor Green
$staticContents | ForEach-Object { Write-Host "  - $($_.Name) ($([math]::round($_.Length / 1MB, 2)) MB)" }
Write-Host "=======================================================" -ForegroundColor Cyan
