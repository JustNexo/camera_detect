param(
    [string]$ExeName = "QRPassClient",
    [string]$ReleaseName = "qrpass_client_ffo4_release",
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\build_exe.ps1")) {
    throw "Run this script from qrpass_client directory."
}

# 1) Build exe
$buildArgs = @(
    "-ExecutionPolicy", "Bypass",
    "-File", ".\build_exe.ps1",
    "-EntryPoint", "main.py",
    "-ExeName", $ExeName
)
if ($OneFile) {
    $buildArgs += "-OneFile"
}
powershell @buildArgs

# 2) Prepare release folder
$releaseDir = Join-Path (Get-Location) "release\$ReleaseName"
if (Test-Path $releaseDir) {
    Remove-Item $releaseDir -Recurse -Force
}
New-Item -ItemType Directory -Path $releaseDir | Out-Null

if ($OneFile) {
    Copy-Item "dist\$ExeName.exe" $releaseDir -Force
} else {
    if (-not (Test-Path "dist\$ExeName")) {
        throw "Build output missing: dist\$ExeName"
    }
    Copy-Item "dist\$ExeName" $releaseDir -Recurse -Force
}

# 3) Add config/templates and helper files
if (Test-Path ".\.env.example") {
    Copy-Item ".\.env.example" (Join-Path $releaseDir ".env") -Force
}
if (Test-Path ".\sql\update_cameras_ffo4_from_xlsx.sql") {
    Copy-Item ".\sql\update_cameras_ffo4_from_xlsx.sql" $releaseDir -Force
}
if (Test-Path ".\best.pt") {
    Copy-Item ".\best.pt" $releaseDir -Force
}

$runBat = @"
@echo off
chcp 65001 >nul
setlocal
cd /d %~dp0

REM Если собран onefile:
if exist "%~dp0$ExeName.exe" (
  "$ExeName.exe"
  goto :eof
)

REM Если собран onedir:
if exist "%~dp0$ExeName\$ExeName.exe" (
  "%~dp0$ExeName\$ExeName.exe"
  goto :eof
)

echo Не найден исполняемый файл $ExeName.exe
pause
"@
Set-Content -Path (Join-Path $releaseDir "run_client.bat") -Value $runBat -Encoding UTF8

Write-Host ""
Write-Host "Release package ready:"
Write-Host (Resolve-Path $releaseDir)
Write-Host ""
Write-Host "Copy this folder to Windows mini-PC (no Python needed)."
