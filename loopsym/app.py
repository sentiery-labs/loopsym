"""loopsym.app — 뷰어를 독립 프로그램 창으로 연다.

크로미엄 계열 브라우저의 --app 모드(주소창/탭 없는 단독 창)를 쓴다 —
추가 의존성 없이 데스크톱 앱처럼 보인다. 크로미엄이 없으면 기본 브라우저 탭.

    loopsym                      # 빈 편집기
    loopsym model.json           # 모델 열기
    loopsym model.json --dt 0.004 --t-end 8
"""

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import webbrowser

_CHROMIUMS = ["google-chrome", "google-chrome-stable", "chromium",
              "chromium-browser", "brave-browser", "microsoft-edge",
              "chrome", "msedge"]
_MAC_APPS = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
             "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
# Windows 는 PATH 에 없는 게 보통 — 표준 설치 경로 직접 확인.
# Edge 는 Win10/11 기본 내장이라 사실상 항상 잡힌다.
_WIN_APPS = [r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
             r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
             r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
             r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
             r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"]


def _find_chromium():
    for b in _CHROMIUMS:
        p = shutil.which(b)
        if p:
            return p
    if sys.platform == "darwin":
        for p in _MAC_APPS:
            if os.path.exists(p):
                return p
    if os.name == "nt":
        for raw in _WIN_APPS:
            p = os.path.expandvars(raw)
            if os.path.exists(p):
                return p
    return None


def open_app(model=None, title="loopsym", t_end=None, dt=None,
             save_name=None, html_path=None):
    """모델(경로/dict/Diagram/None=빈 편집기)을 앱 창으로 연다. 반환: HTML 경로."""
    from .core import Diagram
    from .viz import load_json, render_html

    if model is None:
        bd = Diagram()                        # 빈 캔버스 — '초기 모델' 버튼으로 데모 로드 가능
    elif isinstance(model, Diagram):
        bd = model
    else:                                     # 경로 또는 dict
        bd = load_json(model)
        if isinstance(model, str) and save_name is None:
            save_name = os.path.basename(model)   # 저장 = 같은 이름으로 (제출 흐름)

    if html_path is None:
        stem = os.path.splitext(save_name or "loopsym")[0]
        html_path = os.path.join(tempfile.gettempdir(), f"{stem}_viewer.html")
    path = render_html(bd, html_path, title=title, t_end=t_end, dt=dt,
                       save_name=save_name)
    url = pathlib.Path(path).as_uri()          # Windows 드라이브 문자/역슬래시 안전

    chromium = _find_chromium()
    if chromium:
        kw = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if os.name == "nt":                    # 셸 종료와 독립 (플랫폼별 방식)
            kw["creationflags"] = (subprocess.DETACHED_PROCESS
                                   | subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            kw["start_new_session"] = True
        subprocess.Popen([chromium, f"--app={url}"], **kw)
    else:
        webbrowser.open(url)
    return path
