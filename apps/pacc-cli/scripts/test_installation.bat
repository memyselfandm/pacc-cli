@echo off
REM Test PACC installation on Windows

echo PACC Installation Test Suite
echo ============================

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
set "PACC_ROOT=%SCRIPT_DIR%.."

echo.
echo PACC root directory: %PACC_ROOT%

REM Test 1: Direct module execution
echo.
echo Test 1: Direct module execution
cd /d "%PACC_ROOT%"
python -m pacc --version
if %ERRORLEVEL% EQU 0 (
    echo [PASS] Direct module execution works
) else (
    echo [FAIL] Direct module execution failed
)

REM Test 2: Editable installation in virtual environment
echo.
echo Test 2: Editable installation
set "TEMP_VENV=%TEMP%\pacc_test_venv_%RANDOM%"
python -m venv "%TEMP_VENV%"

REM Activate virtual environment
call "%TEMP_VENV%\Scripts\activate.bat"

pip install -e "%PACC_ROOT%"
pacc --version
set EDITABLE_STATUS=%ERRORLEVEL%

REM Deactivate
call "%TEMP_VENV%\Scripts\deactivate.bat"

REM Clean up
rmdir /s /q "%TEMP_VENV%"

if %EDITABLE_STATUS% EQU 0 (
    echo [PASS] Editable installation works
) else (
    echo [FAIL] Editable installation failed
)

REM Test 3: Wheel installation
echo.
echo Test 3: Wheel installation
set "TEMP_BUILD=%TEMP%\pacc_build_%RANDOM%"
mkdir "%TEMP_BUILD%"
cd /d "%TEMP_BUILD%"

REM Build wheel
pip install build
python -m build --wheel "%PACC_ROOT%"

REM Create new venv for wheel test
set "TEMP_VENV2=%TEMP%\pacc_test_venv2_%RANDOM%"
python -m venv "%TEMP_VENV2%"

call "%TEMP_VENV2%\Scripts\activate.bat"

REM Install the wheel
for %%f in (dist\*.whl) do pip install "%%f"

pacc --help | findstr /C:"PACC - Package manager for Claude Code" >nul
set WHEEL_STATUS=%ERRORLEVEL%

call "%TEMP_VENV2%\Scripts\deactivate.bat"

cd /d "%TEMP%"
rmdir /s /q "%TEMP_BUILD%"
rmdir /s /q "%TEMP_VENV2%"

if %WHEEL_STATUS% EQU 0 (
    echo [PASS] Wheel installation works
) else (
    echo [FAIL] Wheel installation failed
)

REM Test 4: Run verification script
echo.
echo Test 4: Full functionality verification
cd /d "%PACC_ROOT%"
python scripts\verify_installation.py
if %ERRORLEVEL% EQU 0 (
    echo [PASS] All functionality checks passed
) else (
    echo [FAIL] Some functionality checks failed
)

echo.
echo Installation tests completed!
pause