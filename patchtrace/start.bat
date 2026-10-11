@echo off
rem Double-click this file (or run it in PowerShell) to start PatchTrace on Windows.
cd /d %~dp0

if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
echo Installing packages (first run only takes a minute)...
pip install -q -r requirements.txt

rem Optional: remove "rem" and add your key to use real Claude fixes.
rem set ANTHROPIC_API_KEY=your-key-here

echo.
echo PatchTrace is starting. Open http://127.0.0.1:8000 in your browser.
echo Press Ctrl+C to stop.
python -m uvicorn backend.main:app --port 8000
