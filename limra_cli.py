"""
LIMRA 문서 검색 CLI 인터페이스
커맨드라인에서 쉽게 검색하고 다운로드할 수 있는 인터페이스
"""

import asyncio
import argparse
import sys
from limra_search_agent import LimraSearchAgent


async def run_search(args):
    """검색 실행"""
    agent = LimraSearchAgent(
        email=args.email,
        password=args.password,
        download_folder=args.output,
        headless=args.headless
    )

    try:
        await agent.initialize()

        if await agent.login():
            print(f"\n✅ 로그인 성공!")

            # 검색 수행
            results = await agent.search_documents(args.query, max_results=args.max)

            print(f"\n📋 검색 결과: {len(results)}개")
            print("-" * 60)

            for i, result in enumerate(results, 1):
                print(f"\n{i}. [{result['type']}] {result['title']}")
                print(f"   {result['url']}")
                if result['description']:
                    print(f"   {result['description'][:100]}...")

            # 다운로드
            if args.download and results:
                print(f"\n📥 {len(results)}개 파일 다운로드 시작...")
                downloaded = await agent.download_all_results()
                print(f"\n✅ {len(downloaded)}개 파일 다운로드 완료")

            # 리포트 저장
            await agent.save_results_report()

        else:
            print("❌ 로그인 실패")
            sys.exit(1)

    finally:
        await agent.close()


async def run_browse(args):
    """연구 섹션 탐색"""
    agent = LimraSearchAgent(
        email=args.email,
        password=args.password,
        download_folder=args.output,
        headless=args.headless
    )

    try:
        await agent.initialize()

        if await agent.login():
            docs = await agent.browse_research_section()

            print(f"\n📚 발견된 문서: {len(docs)}개")
            for i, doc in enumerate(docs[:50], 1):
                print(f"{i}. [{doc['type']}] {doc['title'][:60]}")

            await agent.save_results_report()
        else:
            print("❌ 로그인 실패")
            sys.exit(1)

    finally:
        await agent.close()


def main():
    parser = argparse.ArgumentParser(
        description='LIMRA 문서 검색 및 다운로드 에이전트',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 검색만 수행
  python limra_cli.py search "insurance trends" -e your@email.com -p password

  # 검색 후 다운로드
  python limra_cli.py search "retirement planning" -e your@email.com -p password --download

  # 연구 섹션 탐색
  python limra_cli.py browse -e your@email.com -p password
        """
    )

    # 공통 인자
    parser.add_argument('-e', '--email', default='plopa1535@kyobo.com',
                        help='LIMRA 로그인 이메일')
    parser.add_argument('-p', '--password', default='Kyobo1234!@#$',
                        help='LIMRA 로그인 비밀번호')
    parser.add_argument('-o', '--output', default='./limra_downloads',
                        help='다운로드 폴더 경로')
    parser.add_argument('--headless', action='store_true',
                        help='브라우저 창 숨기기')

    subparsers = parser.add_subparsers(dest='command', help='명령어')

    # search 명령어
    search_parser = subparsers.add_parser('search', help='문서 검색')
    search_parser.add_argument('query', help='검색어')
    search_parser.add_argument('-m', '--max', type=int, default=20,
                               help='최대 결과 수 (기본: 20)')
    search_parser.add_argument('-d', '--download', action='store_true',
                               help='검색 결과 자동 다운로드')

    # browse 명령어
    browse_parser = subparsers.add_parser('browse', help='연구 섹션 탐색')

    args = parser.parse_args()

    if args.command == 'search':
        asyncio.run(run_search(args))
    elif args.command == 'browse':
        asyncio.run(run_browse(args))
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
