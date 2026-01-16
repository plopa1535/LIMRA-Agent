@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ============================================================
echo LIMRA Document Search - Web UI
echo ============================================================
echo.
echo 브라우저에서 http://localhost:5000 접속하세요
echo 종료하려면 Ctrl+C 를 누르세요
echo.
echo ============================================================

python web_app.py

pause
