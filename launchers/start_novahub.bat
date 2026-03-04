@echo off
setlocal
set BASE_DIR=%~dp0\..
cd /d %BASE_DIR%
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate.bat
python main.py hud
