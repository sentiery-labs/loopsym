"""loopsym CLI — 뷰어를 독립 앱 창으로.

    loopsym                              # 빈 편집기
    loopsym course/week08/week08_model.json --dt 0.004 --t-end 3
    python -m loopsym ...                # 동일
(로컬 서버 모드는 기존대로: python -m loopsym.server)
"""

import argparse


def main(argv=None):
    ap = argparse.ArgumentParser(prog="loopsym",
                                 description="loopsym 뷰어를 독립 앱 창으로 연다")
    ap.add_argument("model", nargs="?", default=None,
                    help="모델 JSON 경로 (생략 = 빈 편집기)")
    ap.add_argument("--t-end", type=float, default=None, help="시뮬 종료 시각 기본값")
    ap.add_argument("--dt", type=float, default=None,
                    help="스텝 기본값 (드론 체인은 0.004)")
    ap.add_argument("--title", default=None, help="창 제목")
    a = ap.parse_args(argv)

    from .app import open_app
    title = a.title or (a.model or "loopsym")
    path = open_app(a.model, title=title, t_end=a.t_end, dt=a.dt)
    print("뷰어:", path)


if __name__ == "__main__":
    main()
