"""
LIMRA 문서 검색 및 다운로드 에이전트
- 로그인 후 문서/아티클 검색
- PDF 및 문서 파일 다운로드
"""

import asyncio
import os
import re
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse, quote_plus

from playwright.async_api import async_playwright, Page, Browser, BrowserContext


class LimraSearchAgent:
    """LIMRA 웹사이트 검색 및 다운로드 에이전트"""

    BASE_URL = "https://www.limra.com"
    LOGIN_URL = "https://www.limra.com/login/"
    SEARCH_URL = "https://www.limra.com/en/search/"
    RESEARCH_URLS = [
        "https://www.limra.com/en/research/",
        "https://www.limra.com/en/research/insurance/",
        "https://www.limra.com/en/research/retirement/",
        "https://www.limra.com/en/research/annuities/",
        "https://www.limra.com/en/research/workplace-benefits/",
    ]

    def __init__(
        self,
        email: str,
        password: str,
        download_folder: str = "./downloads",
        headless: bool = False  # 디버깅을 위해 기본값 False
    ):
        self.email = email
        self.password = password
        self.download_folder = Path(download_folder)
        self.headless = headless
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None
        self.is_logged_in = False

        # 다운로드 폴더 생성
        self.download_folder.mkdir(parents=True, exist_ok=True)

        # 검색 결과 저장
        self.search_results = []

    async def initialize(self):
        """브라우저 초기화"""
        print("[*] 브라우저 초기화 중...")
        self._playwright = await async_playwright().start()

        self.browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-pdf-viewer',  # PDF 뷰어 비활성화
                '--disable-popup-blocking',  # 팝업 차단 비활성화
                '--disable-save-password-bubble',  # 비밀번호 저장 팝업 비활성화
                f'--download-default-directory={str(self.download_folder.absolute())}',  # 기본 다운로드 경로
                '--disable-download-notification',  # 다운로드 알림 비활성화
            ],
            downloads_path=str(self.download_folder.absolute())  # Playwright 다운로드 경로
        )

        # PDF 자동 다운로드 설정
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            accept_downloads=True,
        )

        # 메인 페이지 생성
        self.page = await self.context.new_page()

        # CDP를 통해 메인 페이지에 자동 다운로드 설정
        self._cdp_session = await self.context.new_cdp_session(self.page)
        await self._cdp_session.send('Page.setDownloadBehavior', {
            'behavior': 'allow',
            'downloadPath': str(self.download_folder.absolute())
        })

        # Browser 레벨 다운로드 설정 추가
        await self._cdp_session.send('Browser.setDownloadBehavior', {
            'behavior': 'allow',
            'downloadPath': str(self.download_folder.absolute()),
            'eventsEnabled': True
        })

        # 자동화 감지 우회
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        print("[OK] 브라우저 초기화 완료")

    async def login(self) -> bool:
        """LIMRA 웹사이트 로그인 (2단계 로그인 지원)"""
        print(f"[*] 로그인 시도 중... ({self.email})")

        try:
            # 로그인 페이지로 이동
            await self.page.goto(self.LOGIN_URL, wait_until='networkidle', timeout=60000)
            await asyncio.sleep(3)

            # 현재 URL 확인 (리다이렉트 될 수 있음)
            current_url = self.page.url
            print(f"[>] 현재 페이지: {current_url}")

            # === 1단계: 이메일 입력 ===
            print("\n[1단계] 이메일 입력...")

            # 이메일 입력 필드 찾기
            email_selectors = [
                'input[type="email"]',
                'input[type="text"]',
                'input[name="email"]',
                'input[name="Email"]',
                'input[name="username"]',
                'input[name="Username"]',
                'input[id="email"]',
                'input[id="Email"]',
                '#Email',
                '.email-input',
                'input[placeholder*="email" i]',
                'input[placeholder*="이메일" i]',
                'input:visible',
            ]

            email_input = None
            for selector in email_selectors:
                try:
                    email_input = await self.page.wait_for_selector(selector, timeout=3000)
                    if email_input and await email_input.is_visible():
                        print(f"[OK] 이메일 필드 발견: {selector}")
                        break
                except:
                    continue

            if not email_input:
                # 페이지 소스 저장하여 디버깅
                html = await self.page.content()
                debug_path = self.download_folder / "debug_login_page.html"
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(html)
                print(f"[WARN] 이메일 필드를 찾을 수 없습니다. 페이지 소스 저장됨: {debug_path}")

                # 스크린샷 저장
                screenshot_path = self.download_folder / "debug_login_screenshot.png"
                await self.page.screenshot(path=str(screenshot_path))
                print(f"[IMG] 스크린샷 저장됨: {screenshot_path}")
                return False

            # 이메일 입력
            await email_input.fill(self.email)
            await asyncio.sleep(1)

            # 로그인/다음 버튼 클릭 (1단계)
            first_button_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("로그인")',
                'button:has-text("Log In")',
                'button:has-text("Login")',
                'button:has-text("Next")',
                'button:has-text("다음")',
                'button:has-text("Continue")',
                '.btn-primary',
                'button.btn',
            ]

            first_button = None
            for selector in first_button_selectors:
                try:
                    first_button = await self.page.wait_for_selector(selector, timeout=2000)
                    if first_button and await first_button.is_visible():
                        print(f"[OK] 1단계 버튼 발견: {selector}")
                        break
                except:
                    continue

            # 첫 번째 버튼 클릭 (네비게이션 발생 대비)
            try:
                if first_button:
                    # 네비게이션이 발생할 수 있으므로 expect_navigation 사용
                    try:
                        async with self.page.expect_navigation(timeout=15000, wait_until='networkidle'):
                            await first_button.click()
                    except Exception as nav_err:
                        # 네비게이션이 없을 수도 있음 - 무시
                        print(f"  [i] 1단계 클릭 완료 ({type(nav_err).__name__})")
                else:
                    try:
                        async with self.page.expect_navigation(timeout=15000, wait_until='networkidle'):
                            await email_input.press('Enter')
                    except Exception as nav_err:
                        print(f"  [i] Enter 키 완료 ({type(nav_err).__name__})")
            except Exception as click_err:
                print(f"  [WARN] 1단계 버튼 클릭 중 오류: {click_err}")
                # 클릭 오류 시에도 계속 진행

            print("[...] 다음 단계 대기 중...")
            await asyncio.sleep(4)

            try:
                await self.page.wait_for_load_state('networkidle', timeout=30000)
            except:
                pass  # 타임아웃 무시

            # === 2단계: 비밀번호 입력 ===
            print("\n[2단계] 비밀번호 입력...")

            # 비밀번호 필드 찾기
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                'input[name="Password"]',
                '#Password',
                '#password',
                'input[placeholder*="password" i]',
                'input[placeholder*="비밀번호" i]',
            ]

            password_input = None
            for selector in password_selectors:
                try:
                    password_input = await self.page.wait_for_selector(selector, timeout=5000)
                    if password_input and await password_input.is_visible():
                        print(f"[OK] 비밀번호 필드 발견: {selector}")
                        break
                except:
                    continue

            if not password_input:
                print("[WARN] 비밀번호 필드를 찾을 수 없습니다. 스크린샷 저장 중...")
                screenshot_path = self.download_folder / "debug_password_step.png"
                await self.page.screenshot(path=str(screenshot_path))
                print(f"[IMG] 스크린샷 저장됨: {screenshot_path}")

                # 이미 로그인 된 상태일 수 있음
                page_content = await self.page.content()
                if 'logout' in page_content.lower() or 'sign out' in page_content.lower():
                    print("[OK] 이미 로그인된 상태입니다!")
                    self.is_logged_in = True
                    return True
                return False

            # 비밀번호 입력
            await password_input.fill(self.password)
            await asyncio.sleep(1)

            # 로그인 버튼 클릭 (2단계)
            login_button_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("로그인")',
                'button:has-text("Log In")',
                'button:has-text("Login")',
                'button:has-text("Sign In")',
                '.login-button',
                '#loginButton',
                'button.btn-primary',
                'button.btn',
            ]

            login_button = None
            for selector in login_button_selectors:
                try:
                    login_button = await self.page.wait_for_selector(selector, timeout=2000)
                    if login_button and await login_button.is_visible():
                        print(f"[OK] 로그인 버튼 발견: {selector}")
                        break
                except:
                    continue

            # 로그인 버튼 클릭 (네비게이션 발생 시 예외 무시)
            try:
                if login_button:
                    # Promise.all 패턴으로 클릭과 네비게이션 동시 처리
                    async with self.page.expect_navigation(timeout=30000, wait_until='networkidle'):
                        await login_button.click()
                else:
                    async with self.page.expect_navigation(timeout=30000, wait_until='networkidle'):
                        await password_input.press('Enter')
            except Exception as nav_error:
                # 네비게이션 중 요소 분리 오류는 무시 (실제로 로그인 성공했을 가능성)
                print(f"[...] 페이지 네비게이션 중... ({type(nav_error).__name__})")
                await asyncio.sleep(3)

            # 로그인 완료 대기
            print("[...] 로그인 처리 중...")
            await asyncio.sleep(3)

            try:
                await self.page.wait_for_load_state('networkidle', timeout=15000)
            except:
                pass  # 타임아웃 무시

            # 로그인 성공 확인
            current_url = self.page.url
            print(f"[>] 로그인 후 URL: {current_url}")

            page_content = await self.page.content()

            # 로그인 성공 지표 확인
            success_indicators = [
                'logout' in page_content.lower(),
                'sign out' in page_content.lower(),
                'my account' in page_content.lower(),
                'my limra' in page_content.lower(),
                'welcome' in page_content.lower(),
                '로그아웃' in page_content,
                '회원' in page_content,
                'www.limra.com' in current_url and 'login' not in current_url.lower(),
            ]

            if any(success_indicators):
                self.is_logged_in = True
                print("[OK] 로그인 성공!")

                # 쿠키 저장 (세션 유지용)
                cookies = await self.context.cookies()
                cookies_path = self.download_folder / "session_cookies.json"
                with open(cookies_path, 'w') as f:
                    json.dump(cookies, f)
                print(f"[COOKIE] 세션 쿠키 저장됨: {cookies_path}")

                return True
            else:
                # 메인 페이지로 이동해서 다시 확인
                print("[*] 메인 페이지에서 로그인 상태 확인 중...")
                await self.page.goto(self.BASE_URL, wait_until='networkidle', timeout=30000)
                await asyncio.sleep(2)

                page_content = await self.page.content()
                current_url = self.page.url

                if any([
                    'logout' in page_content.lower(),
                    'sign out' in page_content.lower(),
                    'my limra' in page_content.lower(),
                    '로그아웃' in page_content,
                    'limra.com' in current_url and 'login' not in current_url.lower(),
                ]):
                    self.is_logged_in = True
                    print("[OK] 로그인 성공!")
                    return True

                # 추가 확인: 로그인 페이지가 아니면 로그인 성공으로 간주
                if 'www.limra.com' in current_url and 'login' not in current_url.lower():
                    self.is_logged_in = True
                    print("[OK] 로그인 성공! (메인 페이지 확인)")
                    return True

                print("[ERROR] 로그인 실패 - 자격 증명을 확인해주세요")
                screenshot_path = self.download_folder / "login_failed_screenshot.png"
                await self.page.screenshot(path=str(screenshot_path))
                return False

        except Exception as e:
            # 오류가 발생해도 로그인 상태 확인
            print(f"[WARN] 예외 발생: {e}")
            print("[*] 로그인 상태 재확인 중...")

            try:
                await asyncio.sleep(2)
                await self.page.goto(self.BASE_URL, wait_until='networkidle', timeout=30000)
                page_content = await self.page.content()

                if any([
                    'logout' in page_content.lower(),
                    'sign out' in page_content.lower(),
                    'my limra' in page_content.lower(),
                ]):
                    self.is_logged_in = True
                    print("[OK] 로그인 성공!")
                    return True
            except:
                pass

            print("[ERROR] 로그인 실패")
            screenshot_path = self.download_folder / "login_error_screenshot.png"
            try:
                await self.page.screenshot(path=str(screenshot_path))
            except:
                pass
            return False

    async def search_documents(self, query: str, max_results: int = 50) -> list:
        """문서 검색"""
        print(f"\n[SEARCH] 검색 중: '{query}'")

        results = []

        try:
            # 검색 페이지로 이동
            search_url = f"{self.SEARCH_URL}?q={quote_plus(query)}"
            await self.page.goto(search_url, wait_until='networkidle', timeout=60000)
            await asyncio.sleep(3)

            # 검색 결과 파싱
            results = await self._parse_search_results(max_results)

            # 추가 연구 섹션에서도 검색
            for research_url in self.RESEARCH_URLS:
                try:
                    await self.page.goto(research_url, wait_until='networkidle', timeout=30000)
                    await asyncio.sleep(2)

                    # 페이지 내 검색 기능이 있으면 사용
                    search_input = await self.page.query_selector('input[type="search"], input[name="q"], .search-input')
                    if search_input:
                        await search_input.fill(query)
                        await search_input.press('Enter')
                        await asyncio.sleep(3)

                        additional_results = await self._parse_search_results(max_results - len(results))
                        results.extend(additional_results)

                except Exception as e:
                    print(f"[WARN] {research_url} 검색 중 오류: {e}")
                    continue

                if len(results) >= max_results:
                    break

        except Exception as e:
            print(f"[ERROR] 검색 중 오류 발생: {e}")

        # 중복 제거
        seen_urls = set()
        unique_results = []
        for result in results:
            if result['url'] not in seen_urls:
                seen_urls.add(result['url'])
                unique_results.append(result)

        self.search_results = unique_results[:max_results]
        print(f"[OK] 총 {len(self.search_results)}개 결과 발견")

        return self.search_results

    async def _parse_search_results(self, max_results: int) -> list:
        """검색 결과 페이지 파싱"""
        results = []

        # 다양한 결과 컨테이너 셀렉터
        result_selectors = [
            '.search-result',
            '.search-results-item',
            '.result-item',
            'article',
            '.card',
            '.list-item',
            '[class*="result"]',
            '[class*="article"]',
        ]

        for selector in result_selectors:
            items = await self.page.query_selector_all(selector)
            if items:
                print(f"[LIST] {len(items)}개 항목 발견 ({selector})")

                for item in items[:max_results]:
                    try:
                        result = await self._extract_result_info(item)
                        if result:
                            results.append(result)
                    except Exception as e:
                        continue

                if results:
                    break

        # 직접 링크 검색 (PDF, 문서 등)
        all_links = await self.page.query_selector_all('a[href]')
        for link in all_links:
            try:
                href = await link.get_attribute('href')
                text = await link.inner_text()

                if href and self._is_document_link(href):
                    full_url = urljoin(self.BASE_URL, href)
                    results.append({
                        'title': text.strip() or 'Untitled Document',
                        'url': full_url,
                        'type': self._get_document_type(href),
                        'description': ''
                    })
            except:
                continue

        return results

    async def _extract_result_info(self, element) -> dict:
        """개별 검색 결과 정보 추출"""
        try:
            # 제목 추출
            title_el = await element.query_selector('h1, h2, h3, h4, .title, [class*="title"]')
            title = await title_el.inner_text() if title_el else ''

            # 링크 추출
            link_el = await element.query_selector('a[href]')
            url = await link_el.get_attribute('href') if link_el else ''

            if not url:
                return None

            url = urljoin(self.BASE_URL, url)

            # 설명 추출
            desc_el = await element.query_selector('p, .description, .summary, [class*="desc"]')
            description = await desc_el.inner_text() if desc_el else ''

            # 문서 타입 판별
            doc_type = self._get_document_type(url)

            return {
                'title': title.strip(),
                'url': url,
                'type': doc_type,
                'description': description.strip()[:200]
            }
        except:
            return None

    def _is_document_link(self, url: str) -> bool:
        """문서 링크인지 확인"""
        doc_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']
        url_lower = url.lower()
        return any(ext in url_lower for ext in doc_extensions)

    def _get_document_type(self, url: str) -> str:
        """URL에서 문서 타입 추출"""
        url_lower = url.lower()
        if '.pdf' in url_lower:
            return 'PDF'
        elif '.doc' in url_lower:
            return 'Word'
        elif '.xls' in url_lower:
            return 'Excel'
        elif '.ppt' in url_lower:
            return 'PowerPoint'
        else:
            return 'Article'

    async def _dismiss_cookie_banner(self):
        """쿠키 동의 배너 제거/숨기기"""
        try:
            # 쿠키 배너 닫기 버튼 클릭 시도
            cookie_button_selectors = [
                'button:has-text("Accept All Cookies")',
                'button:has-text("Accept All")',
                'button:has-text("Accept")',
                'button:has-text("동의")',
                'button:has-text("모두 수락")',
                '[id*="cookie"] button',
                '[class*="cookie"] button',
                '.cookie-banner button',
                '#onetrust-accept-btn-handler',
                '.onetrust-close-btn-handler',
            ]

            for selector in cookie_button_selectors:
                try:
                    button = await self.page.query_selector(selector)
                    if button and await button.is_visible():
                        await button.click()
                        await asyncio.sleep(1)
                        return
                except:
                    continue

            # 버튼을 못 찾으면 JavaScript로 쿠키 배너 요소 숨기기
            await self.page.evaluate("""
                () => {
                    // 쿠키 관련 요소 숨기기
                    const selectors = [
                        '[id*="cookie"]',
                        '[class*="cookie"]',
                        '[id*="Cookie"]',
                        '[class*="Cookie"]',
                        '[id*="consent"]',
                        '[class*="consent"]',
                        '[id*="onetrust"]',
                        '[class*="onetrust"]',
                        '[id*="gdpr"]',
                        '[class*="gdpr"]',
                        '.cc-banner',
                        '.cookie-notice',
                        '.cookie-popup',
                        '#cookie-law-info-bar',
                    ];

                    selectors.forEach(selector => {
                        document.querySelectorAll(selector).forEach(el => {
                            el.style.display = 'none';
                            el.style.visibility = 'hidden';
                        });
                    });

                    // position:fixed 요소 중 하단에 위치한 배너 숨기기
                    document.querySelectorAll('*').forEach(el => {
                        const style = window.getComputedStyle(el);
                        if (style.position === 'fixed' &&
                            (style.bottom === '0px' || parseInt(style.bottom) < 100)) {
                            const text = el.innerText.toLowerCase();
                            if (text.includes('cookie') || text.includes('accept') ||
                                text.includes('consent') || text.includes('privacy')) {
                                el.style.display = 'none';
                            }
                        }
                    });
                }
            """)
            await asyncio.sleep(0.5)

        except Exception as e:
            # 쿠키 배너 제거 실패해도 계속 진행
            pass

    async def _dismiss_modal_popup(self):
        """모달 팝업 닫기 (LimraModal 등)"""
        try:
            # LIMRA 사이트의 모달 팝업 닫기
            await self.page.evaluate("""
                () => {
                    // LimraModal 및 일반 모달 닫기
                    const modalSelectors = [
                        '#LimraModal',
                        '.modal',
                        '[class*="modal"]',
                        '.mod-wrapper',
                        '.autofill__panel',
                        '[role="dialog"]',
                        '.popup',
                        '.overlay'
                    ];

                    modalSelectors.forEach(selector => {
                        document.querySelectorAll(selector).forEach(el => {
                            el.style.display = 'none';
                            el.style.visibility = 'hidden';
                            el.style.opacity = '0';
                            el.style.pointerEvents = 'none';
                        });
                    });

                    // 닫기 버튼 클릭 시도
                    const closeButtons = document.querySelectorAll(
                        '.close, .modal-close, [aria-label="Close"], .btn-close, ' +
                        'button[class*="close"], .mod-close, .autofill__close'
                    );
                    closeButtons.forEach(btn => {
                        try { btn.click(); } catch(e) {}
                    });

                    // body overflow 복원 (모달이 스크롤 차단한 경우)
                    document.body.style.overflow = 'auto';
                    document.documentElement.style.overflow = 'auto';
                }
            """)
            await asyncio.sleep(0.3)

        except Exception as e:
            # 모달 제거 실패해도 계속 진행
            pass

    async def browse_research_with_filter(
        self,
        keywords: list = None,
        start_year: int = None,
        end_year: int = None,
        auto_download: bool = False
    ) -> list:
        """
        주제 키워드와 연도로 필터링하여 연구 문서 탐색 및 다운로드

        Args:
            keywords: 검색할 주제 키워드 리스트 (예: ["Recruiting", "Retention"])
            start_year: 시작 연도 (예: 2023)
            end_year: 종료 연도 (예: 2024)
            auto_download: True이면 필터링된 문서 자동 다운로드

        Returns:
            필터링된 문서 목록
        """
        print("\n" + "="*60)
        print("[DOC] Research 섹션 탐색 및 필터링")
        print("="*60)

        if keywords:
            print(f"[SEARCH] 주제 키워드: {', '.join(keywords)}")
        if start_year and end_year:
            print(f"[DATE] 기간: {start_year} ~ {end_year}")
        elif start_year:
            print(f"[DATE] 기간: {start_year} 이후")
        elif end_year:
            print(f"[DATE] 기간: {end_year} 이전")
        print("-"*60)

        # 1단계: 모든 문서 수집
        all_documents = await self.browse_research_section()

        # 2단계: 각 문서 페이지에서 날짜 정보 수집 (필요한 경우)
        if start_year or end_year:
            print(f"\n[DATE] 문서 날짜 정보 수집 중... ({len(all_documents)}개)")
            all_documents = await self._collect_document_dates(all_documents)

        # 3단계: 필터링
        filtered_docs = self._filter_documents(all_documents, keywords, start_year, end_year)

        print(f"\n[OK] 필터링 결과: {len(filtered_docs)}개 문서")
        print("-"*60)

        for i, doc in enumerate(filtered_docs[:20], 1):
            year_str = f" ({doc.get('year', '날짜 미상')})" if doc.get('year') else ""
            print(f"{i}. [{doc['type']}] {doc['title'][:60]}{year_str}")

        if len(filtered_docs) > 20:
            print(f"   ... 외 {len(filtered_docs) - 20}개")

        # 4단계: 자동 다운로드
        if auto_download and filtered_docs:
            print(f"\n[DL] {len(filtered_docs)}개 문서 다운로드 시작...")
            self.search_results = filtered_docs
            downloaded = await self.download_all_results()
            print(f"[OK] {len(downloaded)}개 파일 다운로드 완료")

        # 결과 저장
        self.search_results = filtered_docs
        return filtered_docs

    async def _collect_document_dates(self, documents: list) -> list:
        """각 문서 페이지를 방문하여 날짜 정보 수집"""
        updated_docs = []

        for i, doc in enumerate(documents):
            try:
                # 진행 상황 표시
                if (i + 1) % 10 == 0:
                    print(f"  [FILE] {i + 1}/{len(documents)} 문서 확인 중...")

                # 이미 연도 정보가 있으면 스킵
                if doc.get('year'):
                    updated_docs.append(doc)
                    continue

                # 문서 페이지 방문
                await self.page.goto(doc['url'], wait_until='networkidle', timeout=30000)
                await asyncio.sleep(1)

                # 날짜 정보 추출
                year = await self._extract_year_from_page()
                doc['year'] = year
                updated_docs.append(doc)

            except Exception as e:
                doc['year'] = None
                updated_docs.append(doc)
                continue

        return updated_docs

    async def _extract_year_from_page(self) -> int:
        """페이지에서 연도 정보 추출"""
        try:
            # JavaScript로 페이지에서 날짜 정보 찾기
            year = await self.page.evaluate("""
                () => {
                    // 다양한 날짜 패턴 셀렉터
                    const dateSelectors = [
                        '.date', '.publish-date', '.published-date',
                        '[class*="date"]', '[class*="Date"]',
                        'time', '[datetime]',
                        '.meta', '.article-meta', '.post-meta',
                        '.byline', '.info'
                    ];

                    // 연도 패턴 (2020-2029)
                    const yearPattern = /\b(202[0-9]|201[0-9])\b/;

                    // 날짜 셀렉터에서 연도 찾기
                    for (const selector of dateSelectors) {
                        const elements = document.querySelectorAll(selector);
                        for (const el of elements) {
                            const text = el.innerText || el.getAttribute('datetime') || '';
                            const match = text.match(yearPattern);
                            if (match) {
                                return parseInt(match[1]);
                            }
                        }
                    }

                    // 페이지 전체에서 연도 패턴 찾기 (메타 태그 등)
                    const metaTags = document.querySelectorAll('meta[content]');
                    for (const meta of metaTags) {
                        const content = meta.getAttribute('content') || '';
                        const match = content.match(yearPattern);
                        if (match) {
                            return parseInt(match[1]);
                        }
                    }

                    return null;
                }
            """)
            return year
        except:
            return None

    def _filter_documents(
        self,
        documents: list,
        keywords: list = None,
        start_year: int = None,
        end_year: int = None
    ) -> list:
        """문서 목록 필터링"""
        filtered = []

        for doc in documents:
            # 키워드 필터링
            if keywords:
                title_lower = doc['title'].lower()
                keyword_match = any(kw.lower() in title_lower for kw in keywords)
                if not keyword_match:
                    continue

            # 연도 필터링
            doc_year = doc.get('year')
            if doc_year:
                if start_year and doc_year < start_year:
                    continue
                if end_year and doc_year > end_year:
                    continue
            elif start_year or end_year:
                # 연도 정보가 없으면 제외할지 포함할지 선택
                # 여기서는 연도 정보가 없어도 포함 (키워드가 맞으면)
                pass

            filtered.append(doc)

        return filtered

    async def browse_research_section(self) -> list:
        """연구 섹션 탐색하여 실제 문서/보고서 목록 수집"""
        print("\n[DOC] 연구 섹션 탐색 중...")

        all_documents = []

        for research_url in self.RESEARCH_URLS:
            try:
                print(f"  → {research_url}")
                await self.page.goto(research_url, wait_until='networkidle', timeout=30000)
                await asyncio.sleep(2)

                # 실제 문서/보고서 카드/아이템 찾기
                # LIMRA 사이트의 연구 목록 구조에 맞게 셀렉터 지정
                article_selectors = [
                    '.research-item',
                    '.article-item',
                    '.card',
                    '.list-item',
                    'article',
                    '[class*="research"]',
                    '[class*="article"]',
                    '[class*="report"]',
                    '.content-item',
                    '.publication-item',
                ]

                found_articles = []
                for selector in article_selectors:
                    items = await self.page.query_selector_all(selector)
                    if items and len(items) > 0:
                        found_articles = items
                        print(f"    [LIST] {len(items)}개 항목 발견 ({selector})")
                        break

                # 각 아티클에서 링크와 제목 추출
                for item in found_articles:
                    try:
                        # 제목 링크 찾기
                        title_link = await item.query_selector('a[href]')
                        if not title_link:
                            continue

                        href = await title_link.get_attribute('href')
                        text = await title_link.inner_text()

                        if not href or not text.strip():
                            continue

                        full_url = urljoin(self.BASE_URL, href)

                        # 제외할 링크 패턴 (일반 페이지, 언어 설정 등)
                        skip_patterns = [
                            '?epslanguage=',
                            '/en/research/?',
                            '/login',
                            '/search',
                            '#',
                            'javascript:',
                            '/en/research/insurance/?',
                            '/en/research/retirement/?',
                            '/en/research/annuities/?',
                            '/en/research/workplace-benefits/?',
                        ]

                        if any(pattern in full_url for pattern in skip_patterns):
                            continue

                        # 너무 짧은 제목 제외 (네비게이션 링크일 가능성)
                        if len(text.strip()) < 10:
                            continue

                        all_documents.append({
                            'title': text.strip(),
                            'url': full_url,
                            'type': self._get_document_type(href),
                            'description': ''
                        })
                    except:
                        continue

                # 카드/아이템이 없으면 일반 링크에서 추출 (더 엄격한 필터링)
                if not found_articles:
                    links = await self.page.query_selector_all('a[href]')
                    for link in links:
                        try:
                            href = await link.get_attribute('href')
                            text = await link.inner_text()

                            if not href or not text.strip():
                                continue

                            full_url = urljoin(self.BASE_URL, href)

                            # 실제 문서 페이지인지 확인 (더 구체적인 URL 패턴)
                            # 예: /en/research/research-reports/report-name/
                            url_lower = full_url.lower()

                            # PDF 직접 링크
                            if '.pdf' in url_lower:
                                all_documents.append({
                                    'title': text.strip() or 'PDF Document',
                                    'url': full_url,
                                    'type': 'PDF',
                                    'description': ''
                                })
                                continue

                            # 구체적인 문서 페이지 패턴 (URL에 여러 경로 세그먼트가 있어야 함)
                            path_segments = [s for s in urlparse(full_url).path.split('/') if s]
                            if len(path_segments) >= 3:  # 예: /en/research/report-title/
                                # 제외 패턴 확인
                                skip_patterns = [
                                    '?epslanguage=',
                                    '/login',
                                    '/search',
                                    '#',
                                    'javascript:',
                                ]
                                if any(pattern in full_url for pattern in skip_patterns):
                                    continue

                                # 짧은 제목 제외
                                if len(text.strip()) < 15:
                                    continue

                                all_documents.append({
                                    'title': text.strip(),
                                    'url': full_url,
                                    'type': 'Article',
                                    'description': ''
                                })
                        except:
                            continue

            except Exception as e:
                print(f"  [WARN] 오류: {e}")
                continue

        # 중복 제거
        seen = set()
        unique_docs = []
        for doc in all_documents:
            if doc['url'] not in seen and doc['title'] not in seen:
                seen.add(doc['url'])
                seen.add(doc['title'])
                unique_docs.append(doc)

        print(f"[OK] 총 {len(unique_docs)}개 실제 문서 발견")
        return unique_docs

    async def download_document(self, url: str, filename: str = None) -> str:
        """문서 다운로드 - 실제 파일 다운로드 우선"""
        try:
            print(f"[DL] 다운로드 중: {url}")

            # 파일명 생성
            if not filename:
                parsed = urlparse(url)
                filename = os.path.basename(parsed.path) or 'document'
                # 파일명 정리
                filename = re.sub(r'[<>:"/\\|?*]', '_', filename)

            # 확장자가 없으면 추가
            if '.' not in filename:
                filename += '.pdf'

            filepath = self.download_folder / filename

            # 중복 파일명 처리
            counter = 1
            original_filepath = filepath
            while filepath.exists():
                stem = original_filepath.stem
                suffix = original_filepath.suffix
                filepath = self.download_folder / f"{stem}_{counter}{suffix}"
                counter += 1

            # 페이지 방문
            await self.page.goto(url, wait_until='networkidle', timeout=60000)
            await asyncio.sleep(2)

            # 쿠키 배너 및 모달 팝업 제거
            await self._dismiss_cookie_banner()
            await self._dismiss_modal_popup()

            # 페이지에서 다운로드 가능한 파일 링크/버튼 찾기
            download_element = await self._find_download_element()

            if download_element:
                # 실제 파일 다운로드 - 클릭 방식
                try:
                    print(f"  [LINK] 다운로드 링크 발견, 클릭 중...")

                    # 모달 다시 확인 후 닫기
                    await self._dismiss_modal_popup()

                    # force 옵션으로 클릭 시도
                    async with self.page.expect_download(timeout=60000) as download_info:
                        await download_element.click(force=True)

                    download = await download_info.value

                    # 다운로드 완료 대기
                    await download.path()

                    # 원본 파일명 사용
                    suggested_filename = download.suggested_filename
                    if suggested_filename:
                        # 확장자 유지
                        ext = Path(suggested_filename).suffix
                        if ext:
                            filepath = filepath.with_suffix(ext)

                    await download.save_as(str(filepath))
                    print(f"[OK] 실제 파일 저장됨: {filepath}")
                    return str(filepath)

                except Exception as e:
                    print(f"[WARN] 클릭 다운로드 실패: {e}")

            # 직접 PDF 링크로 다운로드 시도
            pdf_link = await self._find_pdf_url()
            if pdf_link:
                try:
                    print(f"  [LINK] PDF URL 발견: {pdf_link[:50]}...")

                    async with self.page.expect_download(timeout=60000) as download_info:
                        # JavaScript로 다운로드 트리거
                        await self.page.evaluate(f'''
                            () => {{
                                const a = document.createElement('a');
                                a.href = "{pdf_link}";
                                a.download = "";
                                a.style.display = "none";
                                document.body.appendChild(a);
                                a.click();
                                document.body.removeChild(a);
                            }}
                        ''')

                    download = await download_info.value
                    suggested_filename = download.suggested_filename
                    if suggested_filename:
                        ext = Path(suggested_filename).suffix
                        if ext:
                            filepath = filepath.with_suffix(ext)

                    await download.save_as(str(filepath))
                    print(f"[OK] 실제 파일 저장됨: {filepath}")
                    return str(filepath)

                except Exception as e:
                    print(f"[WARN] PDF URL 다운로드 실패: {e}")

            # 다운로드 링크를 찾지 못한 경우 - 페이지 PDF로 저장 (폴백)
            print(f"[WARN] 다운로드 링크 없음, 페이지 PDF로 저장")
            if filepath.suffix != '.pdf':
                filepath = filepath.with_suffix('.pdf')

            await self._dismiss_cookie_banner()
            await self.page.pdf(path=str(filepath))

            print(f"[OK] 페이지 캡처 저장됨: {filepath}")
            return str(filepath)

        except Exception as e:
            print(f"[ERROR] 다운로드 실패: {e}")
            return None

    async def _find_download_element(self):
        """페이지에서 클릭 가능한 다운로드 요소 찾기"""
        try:
            # 다운로드 버튼/링크 셀렉터들 (클릭용)
            download_selectors = [
                # PDF 직접 링크
                'a[href$=".pdf"]',
                'a[href*=".pdf?"]',
                'a[href*="/pdf/"]',
                # 다운로드 속성이 있는 링크
                'a[download]',
                # 텍스트 기반
                'a:has-text("Download PDF")',
                'a:has-text("Download Report")',
                'a:has-text("Download")',
                'a:has-text("다운로드")',
                'a:has-text("PDF")',
                # 클래스 기반
                'a[class*="download"]',
                'a[class*="Download"]',
                '.download-link',
                '.download-btn',
                '.pdf-download',
                # 버튼 형태
                'button:has-text("Download")',
                'button:has-text("다운로드")',
                # 아이콘이 있는 링크 (LIMRA 스타일)
                'a[href*="download"]',
                'a[href*="Download"]',
            ]

            for selector in download_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    for element in elements:
                        if await element.is_visible():
                            href = await element.get_attribute('href')
                            # PDF 링크인지 확인
                            if href and ('.pdf' in href.lower() or 'download' in href.lower()):
                                return element
                except:
                    continue

            return None

        except Exception as e:
            return None

    async def _find_pdf_url(self) -> str:
        """페이지에서 PDF URL 찾기"""
        try:
            # JavaScript로 모든 PDF 링크 수집
            pdf_urls = await self.page.evaluate("""
                () => {
                    const urls = [];
                    // 모든 a 태그에서 PDF 링크 찾기
                    document.querySelectorAll('a[href]').forEach(a => {
                        const href = a.href || '';
                        if (href.toLowerCase().includes('.pdf')) {
                            urls.push(href);
                        }
                    });
                    // iframe 내부도 확인
                    document.querySelectorAll('iframe').forEach(iframe => {
                        try {
                            const src = iframe.src || '';
                            if (src.toLowerCase().includes('.pdf')) {
                                urls.push(src);
                            }
                        } catch(e) {}
                    });
                    // embed/object 태그 확인
                    document.querySelectorAll('embed[src], object[data]').forEach(el => {
                        const src = el.src || el.data || '';
                        if (src.toLowerCase().includes('.pdf')) {
                            urls.push(src);
                        }
                    });
                    return urls;
                }
            """)

            # 첫 번째 유효한 PDF URL 반환
            for url in pdf_urls:
                if url and '.pdf' in url.lower():
                    return url

            return None

        except Exception as e:
            return None

    async def download_all_results(self) -> list:
        """검색된 모든 결과 다운로드"""
        print(f"\n[PKG] {len(self.search_results)}개 문서 다운로드 시작...")

        downloaded_files = []

        for i, result in enumerate(self.search_results, 1):
            print(f"\n[{i}/{len(self.search_results)}] {result['title'][:50]}...")

            # 파일명 생성
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', result['title'])[:100]
            extension = '.pdf' if result['type'] == 'PDF' else '.pdf'
            filename = f"{safe_title}{extension}"

            filepath = await self.download_document(result['url'], filename)
            if filepath:
                downloaded_files.append({
                    'title': result['title'],
                    'url': result['url'],
                    'filepath': filepath
                })

            # 요청 간 딜레이
            await asyncio.sleep(2)

        print(f"\n[OK] 총 {len(downloaded_files)}개 파일 다운로드 완료")
        return downloaded_files

    async def save_results_report(self):
        """검색 결과 리포트 저장"""
        report_path = self.download_folder / f"search_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        report = {
            'search_date': datetime.now().isoformat(),
            'total_results': len(self.search_results),
            'results': self.search_results
        }

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"[REPORT] 검색 리포트 저장됨: {report_path}")
        return report_path

    async def close(self):
        """브라우저 종료"""
        if self.browser:
            await self.browser.close()
            print("[CLOSE] 브라우저 종료됨")


async def main():
    """메인 실행 함수"""
    # 설정
    EMAIL = "plopa1535@kyobo.com"
    PASSWORD = "Kyobo1234!@#$"
    DOWNLOAD_FOLDER = "./limra_downloads"

    # 에이전트 생성
    agent = LimraSearchAgent(
        email=EMAIL,
        password=PASSWORD,
        download_folder=DOWNLOAD_FOLDER,
        headless=False  # 브라우저 창 표시 (디버깅용)
    )

    try:
        # 초기화
        await agent.initialize()

        # 로그인
        login_success = await agent.login()

        if login_success:
            print("\n" + "="*50)
            print("로그인 성공! 이제 검색을 수행할 수 있습니다.")
            print("="*50)

            # 메뉴 선택
            print("\n[MENU] 작업을 선택하세요:")
            print("1. 키워드 검색")
            print("2. Research 섹션 탐색 (주제/연도 필터링)")
            print("3. Research 섹션 전체 탐색")

            menu_choice = input("\n선택 (1/2/3): ").strip()

            if menu_choice == '1':
                # 키워드 검색
                search_query = input("\n[SEARCH] 검색어를 입력하세요: ").strip()

                if search_query:
                    results = await agent.search_documents(search_query, max_results=20)

                    print("\n[LIST] 검색 결과:")
                    print("-" * 50)
                    for i, result in enumerate(results, 1):
                        print(f"{i}. [{result['type']}] {result['title'][:60]}")
                        print(f"   URL: {result['url']}")
                        print()

                    if results:
                        download_choice = input("\n모든 결과를 다운로드하시겠습니까? (y/n): ").strip().lower()
                        if download_choice == 'y':
                            downloaded = await agent.download_all_results()
                            print(f"\n[OK] {len(downloaded)}개 파일이 {DOWNLOAD_FOLDER}에 저장되었습니다.")

                    await agent.save_results_report()

            elif menu_choice == '2':
                # Research 섹션 탐색 (주제/연도 필터링)
                print("\n" + "="*50)
                print("[DOC] Research 섹션 필터링 검색")
                print("="*50)

                # 주제 키워드 입력
                print("\n[SEARCH] 주제 키워드를 입력하세요")
                print("   (쉼표로 구분, 예: Recruiting, Retention, Agent)")
                print("   (전체 검색은 빈칸으로 Enter)")
                keywords_input = input("   키워드: ").strip()

                keywords = None
                if keywords_input:
                    keywords = [kw.strip() for kw in keywords_input.split(',') if kw.strip()]

                # 연도 범위 입력
                print("\n[DATE] 연도 범위를 입력하세요")
                print("   (전체 기간은 빈칸으로 Enter)")

                start_year_input = input("   시작 연도 (예: 2023): ").strip()
                end_year_input = input("   종료 연도 (예: 2024): ").strip()

                start_year = int(start_year_input) if start_year_input.isdigit() else None
                end_year = int(end_year_input) if end_year_input.isdigit() else None

                # 자동 다운로드 여부
                auto_download = input("\n[DL] 필터링된 문서를 자동 다운로드할까요? (y/n): ").strip().lower() == 'y'

                # 필터링 검색 실행
                filtered_docs = await agent.browse_research_with_filter(
                    keywords=keywords,
                    start_year=start_year,
                    end_year=end_year,
                    auto_download=auto_download
                )

                # 결과 저장
                if filtered_docs:
                    filter_desc = []
                    if keywords:
                        filter_desc.append(f"keywords_{'_'.join(keywords)}")
                    if start_year or end_year:
                        filter_desc.append(f"{start_year or 'any'}-{end_year or 'any'}")

                    report_name = f"filtered_research_{'_'.join(filter_desc)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    report_path = agent.download_folder / report_name

                    with open(report_path, 'w', encoding='utf-8') as f:
                        json.dump({
                            'filter_date': datetime.now().isoformat(),
                            'keywords': keywords,
                            'start_year': start_year,
                            'end_year': end_year,
                            'total_documents': len(filtered_docs),
                            'documents': filtered_docs
                        }, f, ensure_ascii=False, indent=2)
                    print(f"\n[FILE] 필터링 결과 저장됨: {report_path}")

                    # 수동 다운로드 옵션
                    if not auto_download and filtered_docs:
                        download_choice = input("\n결과를 다운로드하시겠습니까? (y/n): ").strip().lower()
                        if download_choice == 'y':
                            max_download = input(f"다운로드할 최대 문서 수 (기본: 전체 {len(filtered_docs)}개): ").strip()
                            max_download = int(max_download) if max_download.isdigit() else len(filtered_docs)

                            agent.search_results = filtered_docs[:max_download]
                            downloaded = await agent.download_all_results()
                            print(f"\n[OK] {len(downloaded)}개 파일이 {DOWNLOAD_FOLDER}에 저장되었습니다.")

            elif menu_choice == '3':
                # 연구 섹션 전체 탐색
                docs = await agent.browse_research_section()
                print(f"\n[DOC] {len(docs)}개의 연구 문서를 발견했습니다.")

                research_report_path = agent.download_folder / f"research_documents_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(research_report_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        'scan_date': datetime.now().isoformat(),
                        'total_documents': len(docs),
                        'documents': docs
                    }, f, ensure_ascii=False, indent=2)
                print(f"[FILE] 연구 문서 목록 저장됨: {research_report_path}")

                if docs:
                    download_research = input("\n연구 문서를 다운로드하시겠습니까? (y/n): ").strip().lower()
                    if download_research == 'y':
                        max_download = input(f"다운로드할 최대 문서 수 (기본: 20, 전체: {len(docs)}): ").strip()
                        max_download = int(max_download) if max_download.isdigit() else 20

                        agent.search_results = docs[:max_download]
                        downloaded = await agent.download_all_results()
                        print(f"\n[OK] {len(downloaded)}개 연구 문서가 {DOWNLOAD_FOLDER}에 저장되었습니다.")

        else:
            print("\n[ERROR] 로그인에 실패했습니다. 자격 증명을 확인해주세요.")
            print("   다운로드 폴더에서 디버그 스크린샷을 확인하세요.")

    except KeyboardInterrupt:
        print("\n\n[WARN] 사용자에 의해 중단됨")

    except Exception as e:
        print(f"\n[ERROR] 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await agent.close()


if __name__ == "__main__":
    # Windows asyncio 경고 숨기기
    import warnings
    warnings.filterwarnings("ignore", category=ResourceWarning)

    # Windows에서 ProactorEventLoop 관련 경고 방지
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(main())
