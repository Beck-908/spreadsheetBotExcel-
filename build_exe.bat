@echo off
rem Builds the installer: dist\PDF-to-Excel-Bot-Setup-<version>.exe. Send coworkers that one file.
rem Needs Python 3.12+, Node.js 20+ and Inno Setup 6 on this PC (coworkers need none of them).
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    python -m venv .venv || goto :nopython
)
.venv\Scripts\python -m pip install --quiet -r requirements-dev.txt || goto :failed

rem 1. The window's UI: frontend\ (React) builds into frontend\dist.
where npm >nul 2>nul || goto :nonode
pushd frontend
if not exist node_modules (
    call npm install || (popd & goto :failed)
)
call npm run build || (popd & goto :failed)
popd

rem 2. The app as a folder, dist\PDF to Excel Bot\ (starts faster than a one-file exe, and antivirus
rem    and company policies are less likely to block it, since nothing unpacks into the temp folder).
.venv\Scripts\python -m PyInstaller --noconfirm --clean --onedir --windowed --icon installer\app.ico ^
    --collect-data pdfminer --add-data "frontend\dist;ui" --name "PDF to Excel Bot" app.py || goto :failed

rem 3. Microsoft's WebView2 bootstrapper, bundled so Setup can install WebView2 on PCs that lack it.
if not exist installer\redist\MicrosoftEdgeWebview2Setup.exe (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$f = 'installer\redist\MicrosoftEdgeWebview2Setup.exe'; New-Item -ItemType Directory -Force (Split-Path $f) | Out-Null;" ^
        "Invoke-WebRequest 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $f -UseBasicParsing;" ^
        "$s = Get-AuthenticodeSignature $f; if ($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') { Remove-Item $f; Write-Error 'WebView2 bootstrapper signature check failed'; exit 1 }" ^
        || goto :failed
)

rem 4. The installer, with the version from pdf_excel_bot\__init__.py.
for /f "delims=" %%v in ('.venv\Scripts\python -c "from pdf_excel_bot import VERSION; print(VERSION)"') do set VERSION=%%v
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" goto :noinno
"%ISCC%" /Q /DMyAppVersion=%VERSION% "installer\PDF to Excel Bot.iss" || goto :failed
echo.
echo Built: %~dp0dist\PDF-to-Excel-Bot-Setup-%VERSION%.exe
goto :eof

:nopython
echo Python 3.12 or newer is needed to build. Get it from https://www.python.org/downloads/
exit /b 1

:nonode
echo Node.js 20 or newer is needed to build the window. Get it from https://nodejs.org/
exit /b 1

:noinno
echo Inno Setup 6 is needed to build the installer: winget install JRSoftware.InnoSetup --scope user
exit /b 1

:failed
echo Build failed - see the messages above.
exit /b 1
