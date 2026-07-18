"""loopsym CLI — 뷰어를 독립 앱 창으로.

    loopsym                       # PI 데모 (연결 완료 — 실행만 누르면 Scope)
    loopsym --blank               # 빈 편집기
    loopsym --example pendulum    # 번들 예제 (pi | pendulum | discrete_pi)
    loopsym model.json            # 저장한 모델 열기
    python -m loopsym ...         # 동일
(시뮬레이션 스트리밍/실시간/조이스틱은 로컬 서버와 함께: python -m loopsym.server)
"""

import argparse
import json
import sys

# 번들 예제: 이름 -> (t_end, dt) — 각 모델의 회귀 기준 조건
EXAMPLES = {"pi": (10.0, 0.01), "pendulum": (8.0, 0.005), "discrete_pi": (10.0, 0.01)}

EPILOG = """\
실행 형태:
  loopsym                  PI 폐루프 데모가 로드된 뷰어 (첫 실행 권장)
  loopsym --blank          빈 캔버스 (팔레트에서 블록을 놓고 배선)
  loopsym --example NAME   번들 예제: pi | pendulum | discrete_pi
  loopsym MODEL.json       뷰어 '저장' 으로 만든 모델 열기 (저장 파일명 유지)

실행 환경:
  기본은 브라우저 안 Pyodide 가 파이썬 엔진을 그대로 실행한다 — 첫 실행은
  인터넷(CDN)에서 Pyodide 를 내려받는다 (수 초, 이후 캐시). 스트리밍/실시간/
  조이스틱/오프라인은 로컬 서버 모드: `python -m loopsym.server` 를 켜고
  뷰어를 새로고침하면 배지가 'Local Server' 로 바뀐다.
"""


def _load_bundled(name):
    from importlib import resources
    p = resources.files("loopsym").joinpath(f"examples/{name}.json")
    return json.loads(p.read_text(encoding="utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="loopsym", epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="loopsym 뷰어를 독립 앱 창으로 연다 (크로미엄 --app, 폴백 = 브라우저)")
    ap.add_argument("model", nargs="?", default=None,
                    help="모델 JSON 경로 (생략 = PI 데모)")
    ap.add_argument("--blank", action="store_true", help="빈 편집기로 시작")
    ap.add_argument("--example", choices=sorted(EXAMPLES),
                    help="번들 예제 열기 (pi | pendulum | discrete_pi)")
    ap.add_argument("--t-end", type=float, default=None, help="시뮬 종료 시각 기본값")
    ap.add_argument("--dt", type=float, default=None,
                    help="스텝 기본값 (드론 체인은 0.004)")
    ap.add_argument("--title", default=None, help="창 제목")
    a = ap.parse_args(argv)

    if sum(bool(x) for x in (a.model, a.blank, a.example)) > 1:
        ap.error("model 경로, --blank, --example 은 하나만 지정")

    from .app import open_app
    if a.blank:
        model, title, t_end, dt = None, "loopsym", a.t_end, a.dt
    elif a.example or a.model is None:
        name = a.example or "pi"                  # 인자 없음 = PI 데모
        model = _load_bundled(name)
        te, d = EXAMPLES[name]
        title = f"loopsym — {name} 예제"
        t_end = a.t_end if a.t_end is not None else te
        dt = a.dt if a.dt is not None else d
    else:
        model, title, t_end, dt = a.model, a.model, a.t_end, a.dt

    path = open_app(model, title=a.title or title, t_end=t_end, dt=dt)
    print("뷰어:", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
