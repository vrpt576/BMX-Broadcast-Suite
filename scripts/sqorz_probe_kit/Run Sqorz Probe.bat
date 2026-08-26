@echo off
setlocal

echo.
echo Sqorz Probe
echo -----------
echo Checking for Python on this computer...
echo.

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py "%~dp0sqorz_probe.py"
    goto :end
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
    python "%~dp0sqorz_probe.py"
    goto :end
)

echo This computer does not appear to have Python installed.
echo.
echo Please install it from:
echo     https://www.python.org/downloads/
echo.
echo During install, check the box that says "Add python.exe to PATH".
echo Then double-click this file again.

:end
echo.
echo (This window will close when you press a key.)
pause >nul
