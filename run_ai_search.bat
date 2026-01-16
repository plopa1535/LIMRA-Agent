@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ============================================================
echo LIMRA AI Search - Gemini 3 Flash Preview
echo ============================================================
echo.

REM API 키 설정
set GOOGLE_API_KEY=AIzaSyB7yj0QKRBlqdsrG5Q2E6vbGxT95Aevjiw

REM 키워드 입력 받기
set /p KEYWORD="검색 키워드를 입력하세요 (기본값: Retention): "
if "%KEYWORD%"=="" set KEYWORD=Retention

echo.
echo [*] 키워드: %KEYWORD%
echo [*] AI 분석 시작...
echo.

python auto_search_ai.py "%KEYWORD%"

echo.
echo ============================================================
pause
