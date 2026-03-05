@echo off
setlocal
cd /d "%~dp0"
start "" /b "%~dp0.venv\Scripts\pythonw.exe" -m parrator --gui
endlocal
