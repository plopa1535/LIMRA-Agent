# LIMRA 문서 검색 에이전트

LIMRA 웹사이트에 자동으로 로그인하여 문서/아티클을 검색하고 다운로드하는 Python 에이전트입니다.

## 설치 방법

### 방법 1: 배치 파일 사용 (권장)
```
run_agent.bat
```
더블클릭하면 자동으로 설치 및 실행됩니다.

### 방법 2: 수동 설치
```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# 의존성 설치
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium
```

## 사용 방법

### 1. 대화형 모드
```bash
python limra_search_agent.py
```
실행 후 검색어를 입력하면 됩니다.

### 2. CLI 모드

**검색만 수행:**
```bash
python limra_cli.py search "insurance trends"
```

**검색 후 자동 다운로드:**
```bash
python limra_cli.py search "retirement planning" --download
```

**최대 결과 수 지정:**
```bash
python limra_cli.py search "annuities" --max 50 --download
```

**연구 섹션 전체 탐색:**
```bash
python limra_cli.py browse
```

**브라우저 창 숨기기:**
```bash
python limra_cli.py search "workplace benefits" --headless --download
```

## 주요 옵션

| 옵션 | 설명 |
|------|------|
| `-e, --email` | 로그인 이메일 |
| `-p, --password` | 로그인 비밀번호 |
| `-o, --output` | 다운로드 폴더 (기본: ./limra_downloads) |
| `-m, --max` | 최대 결과 수 (기본: 20) |
| `-d, --download` | 검색 결과 자동 다운로드 |
| `--headless` | 브라우저 창 숨기기 |

## 출력 파일

다운로드된 파일과 검색 리포트는 `limra_downloads` 폴더에 저장됩니다.

- `*.pdf` - 다운로드된 PDF 문서
- `search_report_YYYYMMDD_HHMMSS.json` - 검색 결과 리포트
- `session_cookies.json` - 세션 쿠키 (재로그인 시 활용)

## 문제 해결

### 로그인 실패 시
- `limra_downloads/debug_login_screenshot.png` 확인
- `limra_downloads/debug_login_page.html` 확인

### reCAPTCHA 문제
사이트에서 reCAPTCHA 확인을 요구하면 `--headless` 옵션 없이 실행하여 수동으로 처리하세요.

## 주의사항

- 이 에이전트는 개인 학습/연구 목적으로만 사용하세요.
- 과도한 요청은 IP 차단을 유발할 수 있습니다.
- 다운로드된 문서의 저작권을 준수하세요.
