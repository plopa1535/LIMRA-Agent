"""
LIMRA 문서 검색 에이전트 - 웹 인터페이스
Flask 기반 웹 UI
"""

import asyncio
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
from limra_search_agent import LimraSearchAgent

app = Flask(__name__, template_folder='templates', static_folder='static')

# 전역 에이전트 및 상태
agent = None
agent_loop = None  # 에이전트 전용 이벤트 루프
agent_status = {
    'logged_in': False,
    'message': '',
    'progress': '',
    'results': [],
    'is_running': False
}

# 설정
DOWNLOAD_FOLDER = "./limra_downloads"
Path(DOWNLOAD_FOLDER).mkdir(parents=True, exist_ok=True)


def get_or_create_loop():
    """에이전트 전용 이벤트 루프 가져오기 또는 생성"""
    global agent_loop
    if agent_loop is None or agent_loop.is_closed():
        agent_loop = asyncio.new_event_loop()
    return agent_loop


def run_async(coro):
    """비동기 함수를 동기적으로 실행 (동일한 루프 재사용)"""
    loop = get_or_create_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')


@app.route('/api/login', methods=['POST'])
def api_login():
    """로그인 API"""
    global agent, agent_status

    data = request.json
    email = data.get('email', 'plopa1535@kyobo.com')
    password = data.get('password', 'Kyobo1234!@#$')

    agent_status['is_running'] = True
    agent_status['message'] = '로그인 중...'

    try:
        async def do_login():
            global agent
            agent = LimraSearchAgent(
                email=email,
                password=password,
                download_folder=DOWNLOAD_FOLDER,
                headless=False  # 브라우저 표시 (CAPTCHA 대응)
            )
            await agent.initialize()
            success = await agent.login()
            return success

        success = run_async(do_login())

        if success:
            agent_status['logged_in'] = True
            agent_status['message'] = '로그인 성공!'
            return jsonify({'success': True, 'message': '로그인 성공!'})
        else:
            agent_status['message'] = '로그인 실패'
            return jsonify({'success': False, 'message': '로그인 실패. 자격 증명을 확인하세요.'})

    except Exception as e:
        agent_status['message'] = f'오류: {str(e)}'
        return jsonify({'success': False, 'message': str(e)})

    finally:
        agent_status['is_running'] = False


@app.route('/api/search', methods=['POST'])
def api_search():
    """필터링 검색 API"""
    global agent, agent_status

    if not agent or not agent_status['logged_in']:
        return jsonify({'success': False, 'message': '먼저 로그인하세요.'})

    data = request.json
    keywords = data.get('keywords', [])
    start_year = data.get('start_year')
    end_year = data.get('end_year')
    auto_download = data.get('auto_download', False)

    # 문자열을 리스트로 변환
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(',') if k.strip()]

    # 연도를 정수로 변환
    if start_year:
        start_year = int(start_year)
    if end_year:
        end_year = int(end_year)

    agent_status['is_running'] = True
    agent_status['message'] = '검색 중...'
    agent_status['results'] = []

    try:
        async def do_search():
            results = await agent.browse_research_with_filter(
                keywords=keywords if keywords else None,
                start_year=start_year,
                end_year=end_year,
                auto_download=auto_download
            )
            return results

        results = run_async(do_search())

        agent_status['results'] = results
        agent_status['message'] = f'{len(results)}개 문서 발견'

        return jsonify({
            'success': True,
            'message': f'{len(results)}개 문서 발견',
            'results': results
        })

    except Exception as e:
        agent_status['message'] = f'오류: {str(e)}'
        return jsonify({'success': False, 'message': str(e)})

    finally:
        agent_status['is_running'] = False


@app.route('/api/download', methods=['POST'])
def api_download():
    """문서 다운로드 API"""
    global agent, agent_status

    if not agent or not agent_status['logged_in']:
        return jsonify({'success': False, 'message': '먼저 로그인하세요.'})

    data = request.json
    documents = data.get('documents', [])

    if not documents:
        documents = agent_status['results']

    if not documents:
        return jsonify({'success': False, 'message': '다운로드할 문서가 없습니다.'})

    agent_status['is_running'] = True
    agent_status['message'] = f'{len(documents)}개 문서 다운로드 중...'

    try:
        async def do_download():
            agent.search_results = documents
            downloaded = await agent.download_all_results()
            return downloaded

        downloaded = run_async(do_download())

        agent_status['message'] = f'{len(downloaded)}개 파일 다운로드 완료'

        return jsonify({
            'success': True,
            'message': f'{len(downloaded)}개 파일 다운로드 완료',
            'downloaded': downloaded
        })

    except Exception as e:
        agent_status['message'] = f'오류: {str(e)}'
        return jsonify({'success': False, 'message': str(e)})

    finally:
        agent_status['is_running'] = False


@app.route('/api/status')
def api_status():
    """상태 확인 API"""
    return jsonify(agent_status)


@app.route('/api/logout', methods=['POST'])
def api_logout():
    """로그아웃 API"""
    global agent, agent_status, agent_loop

    try:
        if agent:
            run_async(agent.close())

        agent = None
        agent_status['logged_in'] = False
        agent_status['message'] = '로그아웃됨'
        agent_status['results'] = []

        # 이벤트 루프 정리
        if agent_loop and not agent_loop.is_closed():
            agent_loop.close()
            agent_loop = None

        return jsonify({'success': True, 'message': '로그아웃되었습니다.'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/downloads/<path:filename>')
def download_file(filename):
    """다운로드 파일 제공"""
    return send_from_directory(DOWNLOAD_FOLDER, filename)


@app.route('/api/files')
def list_files():
    """다운로드된 파일 목록"""
    files = []
    download_path = Path(DOWNLOAD_FOLDER)

    for f in download_path.glob('*'):
        if f.is_file():
            files.append({
                'name': f.name,
                'size': f.stat().st_size,
                'modified': datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            })

    files.sort(key=lambda x: x['modified'], reverse=True)
    return jsonify(files)


if __name__ == '__main__':
    print("=" * 50)
    print("LIMRA 문서 검색 에이전트 - 웹 UI")
    print("=" * 50)
    print("\n브라우저에서 http://localhost:5000 접속하세요\n")
    app.run(debug=True, port=5000, threaded=True)
