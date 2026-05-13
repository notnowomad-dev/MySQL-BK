@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ========================================
echo  MySQL Backup Scheduler - Setup
echo ========================================
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
echo.

:: Install VC++ Redistributable if missing
if not exist "%SystemRoot%\System32\MSVCP140.dll" (
    echo Visual C++ Redistributable not found.
    if not exist vc_redist.x64.exe (
        echo Downloading vc_redist.x64.exe ^(~25 MB^)...
        powershell -Command "Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile 'vc_redist.x64.exe' -UseBasicParsing"
    )
    echo Installing Visual C++ Redistributable...
    vc_redist.x64.exe /install /quiet /norestart
    echo Done.
) else (
    echo Visual C++ Redistributable already installed.
)
echo.

echo Installing dependencies...
"!PYTHON!" -m pip install --upgrade pip
"!PYTHON!" -m pip install -r requirements.txt

if !errorlevel! neq 0 (
    echo.
    echo ERROR: Failed to install dependencies.
    pause & exit /b 1
)

echo.
echo Setup complete! Run "run.bat" to start the application.
pause
endlocal
