"""배포 wheel 검증 — "배포 ≠ 저장소" 재발 방지 (UX 리뷰 차단 항목 5).

    python tools/check_wheel.py            # sdist/wheel 빌드 + 깨끗한 venv 검증
    python tools/check_wheel.py --no-build # 기존 dist/ 의 wheel 만 검증

검사 내용 (전부 wheel 을 설치한 별도 venv 안에서):
  1. `loopsym --help` 콘솔 스크립트가 존재하고 0 으로 종료
  2. `python -m loopsym --help` 도 동일
  3. __version__ == pyproject 버전
  4. 번들 PI 데모가 wheel 에 실려 있고 render_html 로 렌더된다
  5. 네이티브 시뮬레이션이 회귀 기준값 y(10s)=1.000189 를 재현한다
CI 와 로컬에서 같은 스크립트를 쓴다 (.github/workflows/ci.yml).
"""

import argparse
import glob
import os
import subprocess
import sys
import tempfile
import venv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INNER_CHECK = r"""
import json, sys
import loopsym
from loopsym import Scope, Simulator, load_json
from loopsym.viz import render_html
from importlib import resources

expected = sys.argv[1]
assert loopsym.__version__ == expected, f"__version__={loopsym.__version__} != {expected}"

# 번들 데모가 wheel 에 실려 있는가
p = resources.files("loopsym").joinpath("examples/pi.json")
model = json.loads(p.read_text(encoding="utf-8"))
bd = load_json(model)

# 렌더 (뷰어 HTML 생성 경로)
import tempfile, os
html = render_html(bd, os.path.join(tempfile.gettempdir(), "check_wheel_pi.html"),
                   t_end=10.0, dt=0.01)
assert os.path.getsize(html) > 100_000, "렌더된 HTML 이 비정상적으로 작음"

# 네이티브 시뮬 = 회귀 기준값
bd2 = load_json(model)
sim = Simulator(bd2); sim.run(10.0, 0.01)
sc = [b for b in sim.bd.blocks if isinstance(b, Scope)][0]
y = sc.data[1][-1]
assert abs(y - 1.000189) < 5e-7, f"y(10s)={y}"
print(f"wheel 내부 검증 OK — v{loopsym.__version__}, y(10s)={y:.6f}")
"""


def sh(cmd, **kw):
    disp = [c if len(c) < 60 else c[:40].split("\n")[0] + " …" for c in cmd]
    print("+", " ".join(disp))
    subprocess.run(cmd, check=True, **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-build", action="store_true", help="기존 dist/ 사용")
    a = ap.parse_args()

    if not a.no_build:
        sh([sys.executable, "-m", "build"], cwd=ROOT,
           stdout=subprocess.DEVNULL)
    wheels = sorted(glob.glob(os.path.join(ROOT, "dist", "loopsym-*.whl")))
    if not wheels:
        sys.exit("dist/ 에 wheel 이 없습니다 — --no-build 를 빼고 실행하세요")
    wheel = wheels[-1]
    version = os.path.basename(wheel).split("-")[1]
    print(f"검증 대상: {os.path.basename(wheel)}")

    with tempfile.TemporaryDirectory() as td:
        venv.create(td, with_pip=True)
        bin_dir = "Scripts" if os.name == "nt" else "bin"
        vpy = os.path.join(td, bin_dir, "python")
        sh([vpy, "-m", "pip", "install", "-q", wheel])

        cli = os.path.join(td, bin_dir, "loopsym")
        sh([cli, "--help"], stdout=subprocess.DEVNULL)          # 1. 콘솔 스크립트
        sh([vpy, "-m", "loopsym", "--help"], stdout=subprocess.DEVNULL)  # 2. -m 실행
        sh([vpy, "-c", INNER_CHECK, version])                    # 3~5

    print("PASS — wheel 설치/CLI/데모/시뮬 전부 정상")


if __name__ == "__main__":
    main()
