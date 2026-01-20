"""
LIMRA AI 검색 및 분석 스크립트
Gemini 3 Flash Preview를 사용한 지능형 검색

기능:
1. 키워드 확장 - AI가 관련 키워드 제안
2. 문서 검색 및 다운로드
3. PDF 자동 요약
4. 종합 리포트 생성
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

# Windows asyncio 설정
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from limra_search_agent import LimraSearchAgent
from ai_helper import LimraAIHelper


async def ai_search_and_analyze(
    keyword: str,
    email: str = "plopa1535@kyobo.com",
    password: str = "Kyobo1234!@#$",
    download_folder: str = "C:/Users/CHECK/limra_agent/limra_downloads",
    expand_keywords: bool = True,
    summarize_pdfs: bool = True,
    generate_report: bool = True,
    max_downloads: int = 10,
    language: str = "ko"
):
    """AI 기반 LIMRA 검색 및 분석

    Args:
        keyword: 검색 키워드
        email: LIMRA 계정 이메일
        password: LIMRA 계정 비밀번호
        download_folder: 다운로드 폴더
        expand_keywords: 키워드 확장 사용 여부
        summarize_pdfs: PDF 요약 사용 여부
        generate_report: 종합 리포트 생성 여부
        max_downloads: 최대 다운로드 수
        language: 출력 언어 (ko/en)
    """

    print("=" * 60)
    print("LIMRA AI Search & Analysis")
    print("=" * 60)
    print(f"[*] 키워드: {keyword}")
    print(f"[*] AI 기능: 키워드확장={expand_keywords}, PDF요약={summarize_pdfs}, 리포트={generate_report}")
    print("=" * 60)

    # 결과 저장용
    results = {
        "search_date": datetime.now().isoformat(),
        "original_keyword": keyword,
        "expanded_keywords": None,
        "documents_found": 0,
        "documents_downloaded": 0,
        "pdf_summaries": [],
        "report": None
    }

    # 다운로드 폴더 생성
    Path(download_folder).mkdir(parents=True, exist_ok=True)

    # AI 헬퍼 초기화
    ai = None
    api_key = os.environ.get("GOOGLE_API_KEY")

    if api_key:
        try:
            ai = LimraAIHelper(api_key)
        except Exception as e:
            print(f"[WARN] AI 초기화 실패: {e}")
            print("[*] AI 기능 없이 진행합니다.")
    else:
        print("[WARN] GOOGLE_API_KEY가 설정되지 않았습니다.")
        print("[*] AI 기능 없이 진행합니다.")

    # 1. 키워드 확장
    search_keywords = [keyword]

    if ai and expand_keywords:
        print("\n" + "-" * 40)
        print("[STEP 1] AI 키워드 확장")
        print("-" * 40)

        expanded = ai.expand_keywords(keyword, industry="insurance", count=8)
        results["expanded_keywords"] = expanded

        if expanded.get("all_keywords"):
            search_keywords = expanded["all_keywords"][:5]  # 상위 5개만 사용
            print(f"[OK] 확장된 키워드: {', '.join(search_keywords)}")
        else:
            print("[WARN] 키워드 확장 실패, 원본 키워드만 사용")
    else:
        print("\n[SKIP] 키워드 확장 건너뛰기")

    # 2. 웹 검색
    print("\n" + "-" * 40)
    print("[STEP 2] LIMRA 문서 검색")
    print("-" * 40)

    agent = LimraSearchAgent(
        email=email,
        password=password,
        download_folder=download_folder,
        headless=False
    )

    all_documents = []

    try:
        await agent.initialize()

        # 로그인
        print("[*] LIMRA 로그인 중...")
        login_success = await agent.login()

        if not login_success:
            print("[WARN] 로그인 실패, 30초 대기 후 재시도...")
            await asyncio.sleep(30)
            login_success = await agent.login()

            if not login_success:
                print("[ERROR] 로그인 실패")
                return results

        print("[OK] 로그인 성공!")

        # 각 키워드로 검색 (키워드 검색 기본)
        for kw in search_keywords:
            print(f"\n[SEARCH] '{kw}' 키워드 검색 중...")

            # 키워드 검색 (기본)
            search_docs = await agent.search_documents(kw, max_results=15)

            if search_docs:
                all_documents.extend(search_docs)
                print(f"  [+] {len(search_docs)}개 문서 발견")

        # 중복 제거
        seen_titles = set()
        unique_docs = []
        for doc in all_documents:
            title = doc.get('title', '')
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_docs.append(doc)

        all_documents = unique_docs
        results["documents_found"] = len(all_documents)

        print(f"\n[OK] 총 {len(all_documents)}개 고유 문서 발견")

        # 3. 다운로드
        if all_documents:
            print("\n" + "-" * 40)
            print(f"[STEP 3] 문서 다운로드 (최대 {max_downloads}개)")
            print("-" * 40)

            agent.search_results = all_documents[:max_downloads]
            downloaded = await agent.download_all_results()

            results["documents_downloaded"] = len(downloaded)
            results["downloaded_files"] = downloaded

            print(f"\n[OK] {len(downloaded)}개 파일 다운로드 완료")

    except Exception as e:
        print(f"[ERROR] 검색 중 오류: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await agent.close()

    # 4. PDF 요약
    if ai and summarize_pdfs and results["documents_downloaded"] > 0:
        print("\n" + "-" * 40)
        print("[STEP 4] AI PDF 요약")
        print("-" * 40)

        pdf_files = list(Path(download_folder).glob("*.pdf"))
        # 최근 다운로드된 파일만 (오늘 날짜)
        today = datetime.now().strftime("%Y%m%d")

        summaries = []
        for pdf_path in pdf_files[:max_downloads]:
            print(f"\n[*] 요약 중: {pdf_path.name}")
            summary = ai.summarize_pdf(str(pdf_path), language=language)

            if summary.get("summary"):
                summaries.append(summary)
                print("[OK] 요약 완료")

                # 요약 내용 일부 출력
                preview = summary["summary"][:200] + "..." if len(summary["summary"]) > 200 else summary["summary"]
                print(f"    {preview}")
            else:
                print(f"[WARN] 요약 실패: {summary.get('error')}")

        results["pdf_summaries"] = summaries
        print(f"\n[OK] {len(summaries)}개 PDF 요약 완료")

    # 5. 종합 리포트 생성
    if ai and generate_report and all_documents:
        print("\n" + "-" * 40)
        print("[STEP 5] AI 종합 리포트 생성")
        print("-" * 40)

        # 요약 정보를 문서에 추가
        for doc in all_documents[:max_downloads]:
            for summary in results.get("pdf_summaries", []):
                if doc.get("title") and summary.get("file"):
                    if doc["title"][:30] in summary["file"]:
                        doc["summary"] = summary.get("summary", "")[:500]

        report_result = ai.generate_report(all_documents, keyword, language=language)

        if report_result.get("report"):
            results["report"] = report_result["report"]
            print("[OK] 리포트 생성 완료")
            print("\n" + "=" * 60)
            print("종합 리포트")
            print("=" * 60)
            print(report_result["report"])
        else:
            print(f"[ERROR] 리포트 생성 실패: {report_result.get('error')}")

    # 6. 결과 저장
    print("\n" + "-" * 40)
    print("[STEP 6] 결과 저장")
    print("-" * 40)

    report_filename = f"ai_analysis_{keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path = Path(download_folder) / report_filename

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"[OK] 결과 저장: {report_path}")

    # 마크다운 리포트도 저장
    if results.get("report"):
        md_filename = f"ai_report_{keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        md_path = Path(download_folder) / md_filename

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(f"# LIMRA 검색 분석 리포트\n\n")
            f.write(f"**검색 키워드**: {keyword}\n\n")
            f.write(f"**검색 일시**: {results['search_date']}\n\n")
            f.write(f"**발견 문서**: {results['documents_found']}개\n\n")
            f.write(f"**다운로드**: {results['documents_downloaded']}개\n\n")
            f.write("---\n\n")
            f.write(results["report"])

        print(f"[OK] 마크다운 리포트: {md_path}")

    return results


# 메인 실행
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("LIMRA AI Document Search & Analysis")
    print("=" * 60)

    # 기본 키워드 또는 명령줄 인자
    keyword = sys.argv[1] if len(sys.argv) > 1 else "Retention"

    print(f"\n검색 키워드: {keyword}")
    print("\nAPI 키 확인 중...")

    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        print(f"[OK] GOOGLE_API_KEY 설정됨 (길이: {len(api_key)})")
    else:
        print("[WARN] GOOGLE_API_KEY가 설정되지 않았습니다.")
        print("       AI 기능을 사용하려면 환경변수를 설정하세요:")
        print("       set GOOGLE_API_KEY=your_api_key")

    print("\n" + "-" * 60)

    # 실행
    result = asyncio.run(ai_search_and_analyze(
        keyword=keyword,
        expand_keywords=True,
        summarize_pdfs=True,
        generate_report=True,
        max_downloads=10,
        language="ko"
    ))

    print("\n" + "=" * 60)
    if result.get("report"):
        print("[OK] AI 분석 완료!")
    else:
        print("[OK] 검색 완료! (AI 분석 없음)")
    print("=" * 60)
