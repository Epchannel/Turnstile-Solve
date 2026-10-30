@echo off
setlocal
title Turnstile Solver Server (Port 5072)
echo ====================================================
echo  Khoi dong Turnstile Solver Server (Port 5072)...
echo ====================================================

set PYTHONUTF8=1
cd /d "%~dp0"
python api.py --host 127.0.0.1 --port 5072
if errorlevel 1 pause
endlocal
