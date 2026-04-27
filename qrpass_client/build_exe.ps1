param(
    [string]$EntryPoint = "main.py",
    [string]$ExeName = "QRPassClient",
    [switch]$OneFile,
    [switch]$Windowed
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\requirements.txt")) {
    throw "Run this script from qrpass_client directory."
}

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

$mode = if ($OneFile) { "--onefile" } else { "--onedir" }
$windowFlag = if ($Windowed) { "--windowed" } else { "" }

$args = @(
    "--noconfirm",
    "--clean",
    $mode,
    "--name", $ExeName,
    "--collect-all", "ultralytics",
    "--collect-all", "cv2",
    "--hidden-import", "tkinter",
    "--hidden-import", "requests",
    "--hidden-import", "dotenv",
    $EntryPoint
)

if ($windowFlag -ne "") {
    $args = @($windowFlag) + $args
}

python -m PyInstaller @args

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed. Use clean venv (not broken base/conda env)."
}

$distDir = Join-Path "dist" $ExeName
if ($OneFile) {
    $distDir = "dist"
}

if (-not (Test-Path $distDir)) {
    throw "Build output not found: $distDir"
}

if (Test-Path ".\.env.example") {
    Copy-Item ".\.env.example" $distDir -Force
}
if (Test-Path ".\README.md") {
    Copy-Item ".\README.md" $distDir -Force
}

Write-Host ""
Write-Host "Build completed."
Write-Host "Output:" (Resolve-Path $distDir)
Write-Host "Note: exe hides source files but does not provide cryptographic protection."
