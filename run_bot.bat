@echo off
rem Runs the bot from source. The first run sets up its own Python environment.
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
    echo First run: installing what the bot needs. This takes a minute...
    python -m venv .venv || goto :nopython
    .venv\Scripts\python -m pip install --quiet -r requirements.txt || goto :failed
)
start "" .venv\Scripts\pythonw.exe app.py
goto :eof

:nopython
echo Python 3.12 or newer is needed. Get it from https://www.python.org/downloads/
pause
exit /b 1

:failed
echo Setup failed - see the messages above.
pause
exit /b 1
