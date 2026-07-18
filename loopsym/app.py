"""loopsym.app — 뷰어를 독립 프로그램 창으로 연다.

크로미엄 계열 브라우저의 --app 모드(주소창/탭 없는 단독 창)를 쓴다 —
추가 의존성 없이 데스크톱 앱처럼 보인다. 크로미엄이 없으면 기본 브라우저 탭.

    loopsym                      # 빈 편집기
    loopsym model.json           # 모델 열기
    loopsym model.json --dt 0.004 --t-end 8
"""

import os
import shutil
import subprocess
import sys
import tempfile
import webbrowser

# ponytail: 리눅스/맥 대표 후보만 — 필요해지면 Windows 절대경로 추가
_CHROMIUMS = ["google-chrome", "google-chrome-stable", "chromium",
              "chromium-browser", "brave-browser", "microsoft-edge", "chrome"]
_MAC_APPS = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]


def _find_chromium():
    for b in _CHROMIUMS:
        p = shutil.which(b)
        if p:
            return p
    if sys.platform == "darwin":
        for p in _MAC_APPS:
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
    url = "file://" + path

    chromium = _find_chromium()
    if chromium:
        subprocess.Popen([chromium, f"--app={url}"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)     # 셸 종료와 독립
    else:
        webbrowser.open(url)
    return path
