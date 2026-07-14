"""주차별 노트북(.ipynb) 생성기 — 내용 수정은 여기서 하고 재생성한다.

    python course/tools/gen_notebooks.py
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
COURSE = os.path.dirname(HERE)


def md(s):
    return {"cell_type": "markdown", "metadata": {}, "source": s}


def code(s):
    return {"cell_type": "code", "metadata": {}, "source": s,
            "outputs": [], "execution_count": None}


GRADE = lambda n: code(f"# ✅ 채점 — 전부 초록색이 되면 이번 주 완료!\n!python -m pytest test_week{n:02d}.py -q")

NB = {}

NB[1] = [
    md("# 1주차 — 시뮬레이션이란 무엇인가\n\n"
       "**이번 주에 완성되는 엔진 조각**\n```\n"
       "[신호 함수]  →  (2주) 블록  →  (4주) 다이어그램  →  (6주) 솔버  →  (7주) 폐루프\n"
       " ▲ 여기\n```\n"
       "목표: **신호 = 시간의 함수** 라는 감각. `step(t)`, `ramp(t)`, `sine(t)` 를 만든다.\n\n"
       "> 15주 뒤 당신의 다이어그램이 드론을 날린다 — 오늘은 그 첫 픽셀이다."),
    md("## 이론 요약\n"
       "- 시뮬레이션 = \"시간 t 를 조금씩 흘리며 시스템의 값을 계산하는 것\"\n"
       "- 신호는 `f(t) -> 값` 인 함수로 표현할 수 있다\n"
       "- 파이썬 기초: 변수, 함수 정의(`def`), 기본 인자, 리스트, `for`"),
    code("# 완성된 미래를 미리 구경 — 정식 blocksim 으로 PI 폐루프 (읽기만!)\n"
         "import sys; sys.path.insert(0, '../..')\n"
         "from blocksim import *\n"
         "bd = Diagram()\n"
         "ref = bd.add(Step(t_on=1.0)); err = bd.add(Sum('+-'))\n"
         "ctrl = bd.add(PyFunction('3.0*u0', n_in=1)); plant = bd.add(TransferFunction([1],[1,2,1]))\n"
         "sc = bd.add(Scope(n_in=2, labels=['ref','y']))\n"
         "bd.connect(ref, err[0]); bd.connect(plant, err[1]); bd.connect(err, ctrl)\n"
         "bd.connect(ctrl, plant); bd.connect(ref, sc[0]); bd.connect(plant, sc[1])\n"
         "run(bd, 10.0, 0.01)\n"
         "import matplotlib.pyplot as plt\n"
         "for i, lab in enumerate(sc.labels): plt.plot(sc.t, sc.data[i], label=lab)\n"
         "plt.legend(); plt.grid(True); plt.title('15주 뒤 당신이 이해하게 될 그림')"),
    md("## 실습 — `signals.py` 의 TODO 세 개를 채워라\n"
       "`step` / `ramp` / `sine`. 규약: 스칼라 t 입력 → 스칼라 출력."),
    code("# 내 신호 확인 (signals.py 저장 후 커널 재시작 없이 다시 실행하려면 아래 2줄)\n"
         "import importlib, signals; importlib.reload(signals)\n"
         "import matplotlib.pyplot as plt\n"
         "ts = [i*0.01 for i in range(500)]\n"
         "plt.plot(ts, [signals.step(t) for t in ts], label='step')\n"
         "plt.plot(ts, [signals.ramp(t) for t in ts], label='ramp')\n"
         "plt.plot(ts, [signals.sine(t) for t in ts], label='sine')\n"
         "plt.legend(); plt.grid(True)"),
    md("## 과제\n"
       "step/ramp/sine 세 함수를 t 리스트에 적용해 한 그림에 플롯하고 제출.\n"
       "(위 셀이 그대로 과제 — 채점기는 함수값을 스팟 체크한다)"),
    GRADE(1),
]

NB[2] = [
    md("# 2주차 — 클래스로 블록 만들기\n\n"
       "**이번 주에 완성되는 엔진 조각**\n```\n"
       "신호 함수  →  [블록 = 파라미터 + output()]  →  다이어그램  →  솔버  →  폐루프\n"
       "               ▲ 여기 (Gain, Saturation, Offset)\n```\n"
       "목표: \"블록 = 상태 + 동작을 가진 객체\". 클래스/인스턴스/상속."),
    md("## 이론 요약\n"
       "- 왜 함수가 아니라 클래스인가? **파라미터가 객체 속에 산다** — `Gain(2.0)` 과\n"
       "  `Gain(5.0)` 은 같은 코드, 다른 물건\n"
       "- 규약: `output(t, u, x) -> 튜플`. u 는 입력 튜플, 출력도 튜플 (포트 여러 개 대비)\n"
       "- `Block` 베이스 + 상속: 공통(이름, 포트)은 부모가, 고유(수식)는 자식이"),
    code("import importlib, myblocks; importlib.reload(myblocks)\n"
         "# 제공된 예시 블록 사용해 보기\n"
         "c = myblocks.Constant(3.0)\n"
         "print('Constant(3.0) →', c.output(0.0, (), ()))\n"
         "s = myblocks.Step(t_on=1.0, height=2.0)\n"
         "print('Step  t=0.5 →', s.output(0.5, (), ()), ' t=1.5 →', s.output(1.5, (), ()))"),
    md("## 실습 — `myblocks.py` 의 TODO\n"
       "1. `Gain.output` — 한 줄\n"
       "2. `Saturation.__init__` / `output`\n"
       "3. `Offset` — 클래스 전체 설계 (과제)"),
    code("import importlib, myblocks; importlib.reload(myblocks)\n"
         "g = myblocks.Gain(k=-1.5)\n"
         "print('Gain(-1.5)(2.0) →', g.output(0.0, (2.0,), ()))   # (-3.0,) 이어야 함\n"
         "sat = myblocks.Saturation(lo=-1, hi=1)\n"
         "print('Sat(5.0) →', sat.output(0.0, (5.0,), ()))        # (1,) 이어야 함"),
    GRADE(2),
]

NB[3] = [
    md("# 3주차 — 인터페이스 규약의 힘\n\n"
       "**이번 주에 완성되는 엔진 조각**\n```\n"
       "블록 (Sum · Product · PyFunction 추가)  →  다이어그램  →  솔버  →  폐루프\n"
       " ▲ 여기 — 규약만 지키면 엔진은 블록 종류를 몰라도 된다\n```"),
    md("## 이론 요약\n"
       "- **덕타이핑**: 엔진은 `output()` 만 부른다 — 무슨 블록인지 모른다\n"
       "- 문자열 파라미터가 포트 수를 정한다: `Sum('+-')` → n_in=2 (Simulink 동일)\n"
       "- `PyFunction`: 식 문자열을 `compile`/`eval` — MATLAB Function 블록의 원리\n"
       "- 안전한 eval: `{\"__builtins__\": {}}` 로 위험한 이름 차단"),
    code("import importlib, myblocks; importlib.reload(myblocks)\n"
         "s = myblocks.Sum('+-')\n"
         "print('Sum +- (3,1) →', s.output(0.0, (3.0, 1.0), ()))      # (2.0,)\n"
         "f = myblocks.PyFunction('6.0*(u0-u1) - 2.0*u2', n_in=3)\n"
         "print('PD 식 →', f.output(0.0, (0.8, 0.3, 0.1), ()))"),
    md("## 과제\n"
       "`Sum` / `Product` / `PyFunction` 완성. PyFunction 은 7주차 진자의 심장이 된다."),
    GRADE(3),
]

NB[4] = [
    md("# 4주차 — 다이어그램 = 그래프, 실행 순서 = 위상 정렬\n\n"
       "**이번 주에 완성되는 엔진 조각**\n```\n"
       "블록(완성)  →  [Diagram: connect 검증 + compile 위상정렬]  →  솔버  →  폐루프\n"
       "               ▲ 여기\n```"),
    md("## 이론 요약\n"
       "- 다이어그램 = 그래프: 블록이 노드, 와이어가 간선\n"
       "- 와이어 자료구조: `{(dst블록, dst포트): (src블록, src포트)}`\n"
       "- 불변식: **입력 포트당 드라이버는 하나** — 위반 시도는 connect 에서 즉시 에러\n"
       "- 실행 순서: \"입력을 주는 블록이 먼저\" → 의존 그래프 → Kahn 위상 정렬"),
    code("import importlib, myblocks, mydiagram\n"
         "importlib.reload(myblocks); importlib.reload(mydiagram)\n"
         "bd = mydiagram.Diagram()\n"
         "c = bd.add(myblocks.Constant(1.0, name='c'))\n"
         "a = bd.add(myblocks.Gain(2.0, name='a')); b = bd.add(myblocks.Gain(3.0, name='b'))\n"
         "s = bd.add(myblocks.Sum('++', name='s')); sc = bd.add(myblocks.Scope(name='sc'))\n"
         "bd.connect(c, a); bd.connect(c, b)          # 다이아몬드!\n"
         "bd.connect(a, s[0]); bd.connect(b, s[1]); bd.connect(s, sc)\n"
         "print('실행 순서:', [blk.name for blk in bd.compile()])"),
    md("## 과제\n"
       "잘못된 연결 4종(없는 출력 포트/없는 입력 포트/중복 드라이버/미연결)을\n"
       "전부 에러로 잡아야 채점기를 통과한다."),
    GRADE(4),
]

NB[5] = [
    md("# 5주차 — 피드백과 대수 루프\n\n"
       "**이번 주에 완성되는 엔진 조각**\n```\n"
       "Diagram compile 에 feedthrough 규칙 추가 — 피드백(고리!)이 가능해진다\n"
       "```\n"
       "제어의 본질은 피드백인데 지난주 엔진은 고리를 못 다룬다. 오늘 고친다."),
    md("## 이론 요약\n"
       "- `Gain` 끼리의 고리: y=2x 이면서 x=0.4y — **답이 없는 연립** = 대수 루프\n"
       "- 상태 블록(적분기)의 출력은 '과거의 누적' — 지금 입력이 필요 없다 →\n"
       "  **순서 제약에서 빠진다** → 고리가 끊긴다\n"
       "- 구현은 단 한 줄: `if dst.feedthrough: deps[dst].add(src)` — 이 한 줄이\n"
       "  Simulink 의 폐루프를 가능하게 하는 전부다"),
    code("import importlib, myblocks, mydiagram\n"
         "importlib.reload(myblocks); importlib.reload(mydiagram)\n"
         "# 폐루프: ref → err → ctrl → plant(StateStub) ─┐\n"
         "#          ▲──────────────────────────────────┘\n"
         "bd = mydiagram.Diagram()\n"
         "ref = bd.add(myblocks.Constant(1.0, name='ref'))\n"
         "err = bd.add(myblocks.Sum('+-', name='err'))\n"
         "ctrl = bd.add(myblocks.Gain(3.0, name='ctrl'))\n"
         "plant = bd.add(myblocks.StateStub(name='plant'))\n"
         "bd.connect(ref, err[0]); bd.connect(plant, err[1])\n"
         "bd.connect(err, ctrl); bd.connect(ctrl, plant)\n"
         "print('고리가 있는데도 컴파일 성공:', [b.name for b in bd.compile()])"),
    md("## 과제\n"
       "채점기의 모델 5개(순수 게인 고리/상태 블록 고리/혼합/긴 고리/무고리)가\n"
       "전부 올바르게 판별되어야 한다. 대수 루프 에러 메시지에는 고리 블록\n"
       "이름들을 넣어라 — 미래의 너(디버깅하는 학생)를 위한 배려다."),
    GRADE(5),
]

NB[6] = [
    md("# 6주차 — 시간을 흐르게 하라: 오일러에서 RK4 로\n\n"
       "**이번 주에 완성되는 엔진 조각**\n```\n"
       "블록(Integrator 추가) + Diagram(완성) → [솔버: 오일러/RK4] → 폐루프\n"
       "                                          ▲ 여기 — 엔진의 심장\n```"),
    md("## 이론 요약\n"
       "- `Integrator`: y = x, dx/dt = u — 상태를 가진 첫 블록 (feedthrough=False)\n"
       "- 오일러: `x += dt·f(t,x)` — 오차 ∝ dt (직접 측정해 본다)\n"
       "- RK4: 기울기 4개의 가중 평균 — 오차 ∝ dt⁴ (같은 dt 로 10⁶배 정확)\n"
       "- 진동계에서 오일러는 에너지가 불어나 발산한다 — 안정성은 정확도와 다른 문제"),
    code("import importlib, myblocks, mydiagram, mysim\n"
         "for m in (myblocks, mydiagram, mysim): importlib.reload(m)\n"
         "import math, matplotlib.pyplot as plt\n"
         "# dx/dt = -x, x(0)=1  →  정답 e^-t\n"
         "def decay(method, dt):\n"
         "    bd = mydiagram.Diagram()\n"
         "    z = bd.add(myblocks.Constant(0.0)); neg = bd.add(myblocks.Sum('+-'))\n"
         "    it = bd.add(myblocks.Integrator(x0=1.0)); sc = bd.add(myblocks.Scope())\n"
         "    bd.connect(z, neg[0]); bd.connect(it, neg[1]); bd.connect(neg, it); bd.connect(it, sc)\n"
         "    mysim.simulate(bd, 1.0, dt, method=method)\n"
         "    return abs(sc.data[0][-1] - math.exp(-1))\n"
         "for dt in (0.1, 0.01, 0.001):\n"
         "    print(f'dt={dt}:  euler 오차 {decay(\"euler\", dt):.2e}   rk4 오차 {decay(\"rk4\", dt):.2e}')"),
    md("## 과제\n"
       "1. 위 표를 채워 \"오일러 오차 ∝ dt, RK4 ∝ dt⁴\" 를 확인 (리포트)\n"
       "2. 채점기의 마지막 시험: **네 엔진의 PI 폐루프가 정식 blocksim 과\n"
       "   1e-9 이내로 일치**해야 한다 — 통과하면 네 엔진은 진짜다."),
    GRADE(6),
]

NB[7] = [
    md("# 7주차 — 폐루프 완성 + ★브리지: 내 엔진 ↔ 진짜 blocksim★\n\n"
       "**완성된 엔진 (1~6주차의 전부)**\n```\n"
       "ref → [err] → [PI 제어기] → [플랜트 (적분기 2개)] → scope\n"
       "  ▲──────────────── 피드백 ─────────────────────────┘\n```\n"
       "mybs.py = 지난 6주의 완성본 (제공). 오늘은 이 엔진으로 루프를 닫고,\n"
       "같은 모델을 정식 blocksim 으로 돌려 **6자리까지 같은 숫자**를 확인한다.\n"
       "그 순간이 전반부의 졸업식이다."),
    md("## 이론 요약\n"
       "- P 만: 빠르지만 정상상태 오차가 남는다 (오차가 있어야 출력이 나오므로)\n"
       "- I: 오차를 누적 — 오차가 0 이 될 때까지 밀어붙인다\n"
       "- 플랜트 1/(s²+2s+1) 를 미분방정식 ẍ = u - 2ẋ - x 로 풀어 적분기 2개로 짓는다\n"
       "  (전달함수 블록 없이도 같은 시스템 — 상태공간의 감각)"),
    code("import importlib, mymodel; importlib.reload(mymodel)\n"
         "import mybs, matplotlib.pyplot as plt\n"
         "bd, sc = mymodel.build_pi_loop()\n"
         "mybs.simulate(bd, 10.0, 0.01)\n"
         "plt.plot(sc.t, sc.data[0]); plt.grid(True)\n"
         "print('내 엔진  y(10s) =', f'{sc.data[0][-1]:.6f}',  ' (기준값 1.000189)')"),
    code("# ★브리지: 같은 문제를 정식 blocksim(전달함수 플랜트)으로\n"
         "import sys; sys.path.insert(0, '../..')\n"
         "import blocksim as bs\n"
         "bd2 = bs.Diagram()\n"
         "ref = bd2.add(bs.Step(t_on=1.0)); err = bd2.add(bs.Sum('+-'))\n"
         "kp = bd2.add(bs.Gain(3.0)); it = bd2.add(bs.Integrator()); ki = bd2.add(bs.Gain(2.0))\n"
         "pi = bd2.add(bs.Sum('++')); plant = bd2.add(bs.TransferFunction([1],[1,2,1]))\n"
         "sc2 = bd2.add(bs.Scope(n_in=1))\n"
         "bd2.connect(ref, err[0]); bd2.connect(plant, err[1]); bd2.connect(err, kp)\n"
         "bd2.connect(err, it); bd2.connect(it, ki); bd2.connect(kp, pi[0]); bd2.connect(ki, pi[1])\n"
         "bd2.connect(pi, plant); bd2.connect(plant, sc2)\n"
         "bs.run(bd2, 10.0, 0.01)\n"
         "print('blocksim y(10s) =', f'{sc2.data[0][-1]:.6f}')\n"
         "print('최대차 =', max(abs(a-b) for a,b in zip(sc.data[0], sc2.data[0])))"),
    md("## 과제\n"
       "1. `build_pi_loop` — 위 그림대로 (채점: 기준값 + blocksim 전 구간 대조)\n"
       "2. `build_pendulum` — 비선형 진자 + PD (ex2). θ 가 0.8 에 못 가는 이유를\n"
       "   한 문단으로 쓰라 (가산점: I 를 추가해 오차를 없애 보라)\n\n"
       "**다음 주 예고**: 이제 정식 플랫폼으로 갈아탄다 — 8주차, 6-DoF 쿼드로터가\n"
       "팔레트에서 기다린다. 학기 초의 그 그림이 학기 말에 진짜 기체를 난다."),
    GRADE(7),
]


def main():
    for n, cells in NB.items():
        nb = {
            "cells": cells,
            "metadata": {
                "kernelspec": {"display_name": "Python 3", "language": "python",
                               "name": "python3"},
                "language_info": {"name": "python"},
            },
            "nbformat": 4, "nbformat_minor": 5,
        }
        path = os.path.join(COURSE, f"week{n:02d}", f"week{n:02d}.ipynb")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(nb, f, ensure_ascii=False, indent=1)
        print("wrote", os.path.relpath(path, COURSE))


if __name__ == "__main__":
    main()
