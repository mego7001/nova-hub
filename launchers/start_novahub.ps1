$baseDir = Split-Path -Parent $PSScriptRoot
Set-Location $baseDir
if (-not (Test-Path .venv)) {
  python -m venv .venv
}
& .venv\Scripts\Activate.ps1
python main.py hud
