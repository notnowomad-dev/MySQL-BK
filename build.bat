@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo =====================================================
echo  Database Backup Scheduler - Build EXE
echo =====================================================
echo.

set PYTHON=

:: Try python from PATH first — skip if pip is missing (e.g. Inkscape's bundled Python)
python -m pip --version >nul 2>&1
if !errorlevel! equ 0 set PYTHON=python

:: Scan common install locations newest-first
if not defined PYTHON (
    echo Python in PATH has no pip, scanning known locations...
    for %%P in (
        "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
        "C:\Python313\python.exe"
        "C:\Python312\python.exe"
        "C:\Python311\python.exe"
        "C:\Python310\python.exe"
        "C:\Program Files\Python313\python.exe"
        "C:\Program Files\Python312\python.exe"
        "C:\Program Files\Python311\python.exe"
        "C:\Program Files\Python310\python.exe"
    ) do (
        if not defined PYTHON if exist "%%~P" (
            "%%~P" -m pip --version >nul 2>&1
            if !errorlevel! equ 0 set "PYTHON=%%~P"
        )
    )
)

if not defined PYTHON (
    echo ERROR: No usable Python ^(3.10+^) with pip found.
    echo Install Python from https://python.org and ensure pip is available.
    pause & exit /b 1
)

echo Found: "!PYTHON!"
"!PYTHON!" --version

:: Bundle vc_redist.x64.exe — skip download if already installed or file exists
echo.
echo [1/5] Checking vc_redist.x64.exe...
if exist vc_redist.x64.exe (
    echo Found ^(file already present^).
) else if exist "%SystemRoot%\System32\MSVCP140_1.dll" (
    echo VC++ 2022 already installed on this machine — skipping download.
) else (
    echo Downloading vc_redist.x64.exe ^(~25 MB^)...
    powershell -Command "Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile 'vc_redist.x64.exe' -UseBasicParsing"
    if !errorlevel! neq 0 (
        echo WARNING: Download failed — vc_redist.x64.exe will not be bundled.
        echo          Target machines may need to install VC++ Redistributable manually.
    ) else (
        echo Downloaded.
    )
)

:: Upgrade PyInstaller
echo.
echo [2/5] Upgrading PyInstaller...
"!PYTHON!" -m pip install --upgrade "pyinstaller>=6.0" --quiet
if !errorlevel! neq 0 (
    echo ERROR: Failed to upgrade PyInstaller.
    pause & exit /b 1
)

:: Ensure runtime deps are present
echo.
echo [3/5] Verifying dependencies...
"!PYTHON!" -m pip install -r requirements.txt --quiet
if !errorlevel! neq 0 (
    echo ERROR: Failed to install dependencies.
    pause & exit /b 1
)

:: Clean previous build artefacts
echo.
echo [4/5] Cleaning previous build...
if exist build  rmdir /s /q build
if exist dist   rmdir /s /q dist

:: Build
echo.
echo [5/5] Building executable (this may take a minute)...
"!PYTHON!" -m PyInstaller mysql_backup.spec
if !errorlevel! neq 0 (
    echo.
    echo =====================================================
    echo  Build FAILED. See output above for details.
    echo =====================================================
    pause & exit /b 1
)

echo.
echo =====================================================
echo  Build complete!
echo  Output: dist\Database-Backup-Scheduler.exe
echo =====================================================
echo.
echo You can now copy Database-Backup-Scheduler.exe anywhere
echo and run it without installing Python.
echo.
pause
endlocal
