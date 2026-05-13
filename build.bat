@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo =====================================================
echo  MySQL Backup Scheduler - Build EXE
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

:: Upgrade PyInstaller
echo.
echo [1/4] Upgrading PyInstaller...
"!PYTHON!" -m pip install --upgrade "pyinstaller>=6.0" --quiet
if !errorlevel! neq 0 (
    echo ERROR: Failed to upgrade PyInstaller.
    pause & exit /b 1
)

:: Ensure runtime deps are present
echo.
echo [2/4] Verifying dependencies...
"!PYTHON!" -m pip install -r requirements.txt --quiet
if !errorlevel! neq 0 (
    echo ERROR: Failed to install dependencies.
    pause & exit /b 1
)

:: Clean previous build artefacts
echo.
echo [3/4] Cleaning previous build...
if exist build  rmdir /s /q build
if exist dist   rmdir /s /q dist

:: Build
echo.
echo [4/4] Building executable (this may take a minute)...
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
echo  Output: dist\MySQL-Backup-Scheduler.exe
echo =====================================================
echo.
echo You can now copy MySQL-Backup-Scheduler.exe anywhere
echo and run it without installing Python.
echo.
pause
endlocal
