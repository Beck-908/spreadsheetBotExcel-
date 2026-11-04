@echo off
rem Builds "dist\PDF to Excel Bot.exe" - a single file coworkers can double-click (no Python or Node needed).
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    python -m venv .venv || goto :nopython
)
.venv\Scripts\python -m pip install --quiet -r requirements-dev.txt || goto :failed

rem The window's UI: frontend\ (React) builds into frontend\dist, which goes inside the .exe as ui\.
where npm >nul 2>nul || goto :nonode
pushd frontend
if not exist node_modules (
    call npm install || (popd & goto :failed)
)
call npm run build || (popd & goto :failed)
popd

.venv\Scripts\python -m PyInstaller --noconfirm --clean --onefile --windowed --collect-data pdfminer --add-data "frontend\dist;ui" --name "PDF to Excel Bot" app.py || goto :failed
echo.
echo Built: %~dp0dist\PDF to Excel Bot.exe
goto :eof

:nopython
echo Python 3.12 or newer is needed to build. Get it from https://www.python.org/downloads/
exit /b 1

:nonode
echo Node.js 20 or newer is needed to build the window. Get it from https://nodejs.org/
exit /b 1

:failed
echo Build failed - see the messages above.
exit /b 1
