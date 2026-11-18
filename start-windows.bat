@echo off
setlocal
cd /d "%~dp0"
title Local Transcriber

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-windows.ps1"
if errorlevel 1 (
    echo.
    echo Local Transcriber could not start. See the error above.
    pause
)
