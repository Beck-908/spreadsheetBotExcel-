@echo off
rem Builds "dist\PDF to Excel Bot.exe" - a single file coworkers can double-click (no Python needed).
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    python -m venv .venv || goto :nopython
)
.venv\Scripts\python -m pip install --quiet -r requirements-dev.txt || goto :failed
.venv\Scripts\python -m PyInstaller --noconfirm --clean --onefile --windowed --collect-data pdfminer --name "PDF to Excel Bot" app.py || goto :failed
echo.
echo Built: %~dp0dist\PDF to Excel Bot.exe
goto :eof

:nopython
echo Python 3.12 or newer is needed to build. Get it from https://www.python.org/downloads/
exit /b 1

:failed
echo Build failed - see the messages above.
exit /b 1
