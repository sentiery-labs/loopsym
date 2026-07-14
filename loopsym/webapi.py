"""loopsym.webapi — 뷰어(JS)와 파이썬 엔진 사이의 유일한 통로.

뷰어의 JS 는 시뮬레이션을 하지 않는다. 다이어그램 편집과 결과 그리기만
하고, 실행은 이 모듈의 run_simulation() 하나로 들어온다 (Pyodide 브라우저
런타임/로컬 서버 어느 쪽이든 같은 함수). 그래서 엔진의 의미론은 파이썬
loopsym 한 곳에만 존재한다 — single source of truth.

인터페이스 (JS 쪽과의 계약):
  run_simulation(diagram_json: str, t_end: float, dt: float) -> str
    입력 diagram_json : 뷰어/save_json 의 모델 JSON 문자열 {"blocks": [...], "wires": [...]}
    출력(JSON 문자열):
      {
        "time":    [t0, t1, ...],                     # major step 시각 (모든 Scope 공통)
        "signals": {"<scope 경로>": [[ch0...], [ch1...]]},
        "labels":  {"<scope 경로>": ["ref", "y"]},
        "errors":  []                                 # 실패 시 메시지 1개 이상, 나머지는 빈 값
      }
    scope 경로는 "PI_ctrl/scope" 처럼 서브시스템 경로를 포함한 표시 이름.
"""

import json

from .blocks import Scope, Subsystem
from .sim import run as _run
from .viz import load_json

# 뷰어 실수(dt 오타 등)로 브라우저가 몇 분씩 멈추는 것을 막는 상한
MAX_STEPS = 2_000_000


def _scope_paths(bd, prefix=""):
    """다이어그램을 (flatten 전에) 걸어 Scope 의 경로 이름을 모은다."""
    found = []
    for b in bd.blocks:
        if isinstance(b, Subsystem):
            found += _scope_paths(b.inner, prefix + b.name + "/")
        elif isinstance(b, Scope):
            found.append((prefix + b.name, b))
    return found


def run_simulation(diagram_json, t_end, dt):
    """모델 JSON 을 받아 시뮬레이션하고 결과를 JSON 문자열로 돌려준다."""
    try:
        t_end, dt = float(t_end), float(dt)
        if not (t_end > 0 and dt > 0):
            raise ValueError("t_end, dt 는 양수여야 합니다.")
        if t_end / dt > MAX_STEPS:
            raise ValueError(f"스텝 수가 너무 큽니다 (t_end/dt ≤ {MAX_STEPS:,}).")
        model = json.loads(diagram_json) if isinstance(diagram_json, str) else diagram_json
        bd = load_json(model)
        scopes = _scope_paths(bd)
        _run(bd, t_end, dt)
        return json.dumps({
            "time": list(scopes[0][1].t) if scopes else [],
            "signals": {disp: [list(ch) for ch in s.data] for disp, s in scopes},
            "labels": {disp: list(s.labels) for disp, s in scopes},
            "errors": [],
        })
    except Exception as e:  # 뷰어 상태줄에 그대로 띄울 한 줄 메시지
        return json.dumps(
            {"time": [], "signals": {}, "labels": {}, "errors": [str(e)]},
            ensure_ascii=False)
