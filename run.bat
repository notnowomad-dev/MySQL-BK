@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

set PYTHONW=

:: Try pythonw from PATH first — skip if pip is missing (e.g. Inkscape's bundled Python)
python -m pip --version >nul 2>&1
if !errorlevel! equ 0 set PYTHONW=pythonw

:: Scan common install locations newest-first
if not defined PYTHONW (
    for %%P in (
        "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe"
        "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe"
        "%LOCALAPPDATA%\Programs\Python\Python310\pythonw.exe"
        "C:\Python313\pythonw.exe"
        "C:\Python312\pythonw.exe"
        "C:\Python311\pythonw.exe"
        "C:\Python310\pythonw.exe"
        "C:\Program Files\Python313\pythonw.exe"
        "C:\Program Files\Python312\pythonw.exe"
        "C:\Program Files\Python311\pythonw.exe"
        "C:\Program Files\Python310\pythonw.exe"
    ) do (
        if not defined PYTHONW if exist "%%~P" set "PYTHONW=%%~P"
    )
)

if not defined PYTHONW (
    echo ERROR: No usable Python ^(3.10+^) found.
    echo Install Python from https://python.org
    pause & exit /b 1
)

"!PYTHONW!" main.py
endlocal
