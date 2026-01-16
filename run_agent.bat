@echo off
chcp 65001 > nul
echo ========================================
echo LIMRA Document Search Agent
echo ========================================
echo.

echo [1/3] Installing dependencies...
pip install -q playwright

echo [2/3] Installing Playwright browser...
playwright install chromium

echo [3/3] Starting agent...
echo ========================================
echo.

python limra_search_agent.py

pause
