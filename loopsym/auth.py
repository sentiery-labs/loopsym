"""loopsym.auth — 로컬 서버 접속 키와 출처 검사.

서버 모드는 다이어그램 안의 PyFunction 코드를 이 PC 의 파이썬으로 실행한다
(MATLAB Function 블록처럼 임의 코드 — `__builtins__={}` 는 보안 경계가 아니다).
그런데 브라우저는 아무 웹사이트에서나 ws://localhost 접속을 허용하므로, 아무
검사가 없으면 서버를 켜 둔 동안 방문한 웹페이지가 코드를 보낼 수 있다.

막는 방법 (Jupyter 의 토큰과 같은 생각):
  · 키: 사용자 홈의 파일(~/.loopsym/server_key)에 무작위 키를 한 번 만들어 두고,
    render_html 이 뷰어 HTML 에 심는다. 뷰어는 접속 URL 에 ?key= 로 붙여 보낸다.
    다른 웹사이트는 이 파일도, 로컬 HTML 도 읽을 수 없다.
  · 출처: 키가 새더라도 브라우저의 Origin 이 file:// 뷰어(null)나 localhost
    페이지가 아니면 거부한다. Origin 이 없는 접속은 브라우저가 아닌 클라이언트
    (파이썬 스크립트 등)다.

키를 바꾸려면 `python -m loopsym.server --new-key` (기존 뷰어 HTML 은 다시 만들어야 함).
키 파일 위치는 환경변수 LOOPSYM_HOME 으로 바꿀 수 있다 (테스트가 쓴다).
"""

import os
import secrets
from urllib.parse import urlsplit

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _key_path():
    base = os.environ.get("LOOPSYM_HOME") or os.path.join(os.path.expanduser("~"), ".loopsym")
    return os.path.join(base, "server_key")


def _write_key(path, key):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)   # 본인만 읽기
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(key)
    os.replace(tmp, path)


def server_key():
    """이 사용자의 서버 접속 키. 없으면 만든다."""
    path = _key_path()
    try:
        with open(path, encoding="utf-8") as f:
            key = f.read().strip()
        if key:
            return key
    except FileNotFoundError:
        pass
    key = secrets.token_urlsafe(32)
    _write_key(path, key)
    return key


def new_server_key():
    """키를 새로 만든다 (예전 키를 심은 뷰어 HTML 은 더 이상 서버에 못 붙는다)."""
    key = secrets.token_urlsafe(32)
    _write_key(_key_path(), key)
    return key


def key_ok(given):
    return bool(given) and secrets.compare_digest(given, server_key())


def origin_ok(origin):
    """뷰어가 열릴 수 있는 곳만 허용: file:// (Origin null), localhost 페이지, 비브라우저."""
    if origin is None or origin in ("null", "file://"):
        return True
    try:
        host = urlsplit(origin).hostname
    except ValueError:
        return False
    return host in _LOCAL_HOSTS
