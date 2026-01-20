"""
LIMRA 자동 검색 및 다운로드 스크립트
키워드: Retention
"""

import asyncio
import json
import sys
import warnings
import os
from datetime import datetime
from pathlib import Path

# 출력 버퍼링 비활성화
os.environ['PYTHONUNBUFFERED'] = '1'

# 경고 숨기기
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Windows asyncio 설정 - ProactorEventLoop 사용 (subprocess 지원)
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from limra_search_agent import LimraSearchAgent


async def auto_search_and_download():
    """자동으로 Retention 키워드 검색 및 다운로드"""

    # 설정
    EMAIL = "plopa1535@kyobo.com"
    PASSWORD = "Kyobo1234!@#$"
    DOWNLOAD_FOLDER = "C:/Users/CHECK/limra_agent/limra_downloads"
    KEYWORD = "Retention"

    print("=" * 60)
    print(f"LIMRA 자동 검색 - 키워드: {KEYWORD}")
    print("=" * 60)

    # 다운로드 폴더 생성
    Path(DOWNLOAD_FOLDER).mkdir(parents=True, exist_ok=True)

    # 에이전트 생성
    agent = LimraSearchAgent(
        email=EMAIL,
        password=PASSWORD,
        download_folder=DOWNLOAD_FOLDER,
        headless=False  # 브라우저 표시 (CAPTCHA 대응)
    )

    try:
        # 1. 초기화
        print("\n[1/5] 브라우저 초기화...")
        await agent.initialize()

        # 2. 로그인
        print("\n[2/5] LIMRA 로그인 중...")
        login_success = await agent.login()

        if not login_success:
            print("[ERROR] 로그인 실패! CAPTCHA가 있다면 브라우저에서 직접 해결하세요.")
            print("   30초 대기 후 다시 시도합니다...")
            await asyncio.sleep(30)

            # 로그인 상태 재확인
            login_success = await agent.login()
            if not login_success:
                print("[ERROR] 로그인 재시도 실패")
                return False

        print("[OK] 로그인 성공!")

        # 3. 키워드 검색 (기본)
        print(f"\n[3/5] '{KEYWORD}' 키워드 검색 중...")
        filtered_docs = await agent.search_documents(KEYWORD, max_results=20)

        if not filtered_docs:
            print(f"[WARN] 키워드 검색 결과가 없습니다. Research 섹션 탐색 중...")

            # Research 섹션 탐색 (보조)
            filtered_docs = await agent.browse_research_with_filter(
                keywords=[KEYWORD],
                start_year=None,
                end_year=None,
                auto_download=False
            )

            if not filtered_docs:
                print("[ERROR] 검색 결과가 없습니다.")
                return False

        print(f"\n[OK] 총 {len(filtered_docs)}개 문서 발견")

        # 4. 결과 출력
        print("\n[4/5] 검색 결과:")
        print("-" * 60)
        for i, doc in enumerate(filtered_docs[:10], 1):
            year_str = f" ({doc.get('year', '')})" if doc.get('year') else ""
            print(f"{i}. [{doc['type']}] {doc['title'][:55]}{year_str}")

        if len(filtered_docs) > 10:
            print(f"   ... 외 {len(filtered_docs) - 10}개")

        # 5. 다운로드
        print(f"\n[5/5] {min(len(filtered_docs), 10)}개 문서 다운로드 중...")
        agent.search_results = filtered_docs[:10]  # 최대 10개
        downloaded = await agent.download_all_results()

        print(f"\n[OK] {len(downloaded)}개 파일 다운로드 완료!")
        print(f"   저장 위치: {DOWNLOAD_FOLDER}")

        # 결과 저장
        report_path = Path(DOWNLOAD_FOLDER) / f"retention_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump({
                'search_date': datetime.now().isoformat(),
                'keyword': KEYWORD,
                'total_found': len(filtered_docs),
                'downloaded': len(downloaded),
                'documents': filtered_docs,
                'downloaded_files': downloaded
            }, f, ensure_ascii=False, indent=2)
        print(f"   리포트 저장: {report_path}")

        return True

    except Exception as e:
        print(f"\n[ERROR] 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await agent.close()


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore", category=ResourceWarning)

    print("\n" + "=" * 60)
    print("LIMRA Document Search Agent - Auto Mode")
    print("=" * 60)

    success = asyncio.run(auto_search_and_download())

    if success:
        print("\n" + "=" * 60)
        print("[OK] 작업 완료!")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("[ERROR] 작업 실패")
        print("=" * 60)

    # 자동 실행 모드에서는 input 없이 종료
    # input("\n아무 키나 누르면 종료합니다...")
