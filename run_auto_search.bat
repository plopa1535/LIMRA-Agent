@echo off
chcp 65001 > nul
echo ========================================
echo LIMRA Auto Search - Retention
echo ========================================
echo.

echo [1/2] Checking dependencies...
pip install -q playwright

echo [2/2] Running auto search...
echo ========================================
echo.

python auto_search.py

pause
