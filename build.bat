@echo off
setlocal
cd /d "%~dp0"

echo =====================================================
echo  MySQL Backup Scheduler - Build EXE
echo =====================================================
echo.

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH.
    echo Install Python 3.10+ from https://python.org
    pause & exit /b 1
)
python --version

:: Upgrade PyInstaller to a version that supports the current Python
echo.
echo [1/4] Upgrading PyInstaller...
python -m pip install --upgrade "pyinstaller>=6.0" --quiet
if %errorlevel% neq 0 (
    echo ERROR: Failed to upgrade PyInstaller.
    pause & exit /b 1
)

:: Ensure runtime deps are present
echo.
echo [2/4] Verifying dependencies...
python -m pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
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
python -m PyInstaller mysql_backup.spec
if %errorlevel% neq 0 (
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
