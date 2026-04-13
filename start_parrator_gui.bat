@echo off
setlocal
cd /d "%~dp0"
set "PYW=%~dp0.venv\Scripts\pythonw.exe"

rem Закрываем уже запущенные экземпляры Parrator из этого проекта,
rem чтобы не оставались старые overlay-процессы.
taskkill /f /im Parrator.exe >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=[Regex]::Escape('%PYW%'); Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'pythonw.exe' -and $_.CommandLine -match $p -and ($_.CommandLine -match '-m parrator' -or $_.CommandLine -match 'parrator\\wave_overlay.py') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
timeout /t 1 /nobreak >nul
start "" /b "%PYW%" -m parrator --gui
endlocal
