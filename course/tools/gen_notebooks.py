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
    code("# 완성된 미래를 미리 구경 — 정식 loopsym 으로 PI 폐루프 (읽기만!)\n"
         "import sys; sys.path.insert(0, '../..')\n"
         "from loopsym import *\n"
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
       "2. 채점기의 마지막 시험: **네 엔진의 PI 폐루프가 정식 loopsym 과\n"
       "   1e-9 이내로 일치**해야 한다 — 통과하면 네 엔진은 진짜다."),
    GRADE(6),
]

NB[7] = [
    md("# 7주차 — 폐루프 완성 + ★브리지: 내 엔진 ↔ 진짜 loopsym★\n\n"
       "**완성된 엔진 (1~6주차의 전부)**\n```\n"
       "ref → [err] → [PI 제어기] → [플랜트 (적분기 2개)] → scope\n"
       "  ▲──────────────── 피드백 ─────────────────────────┘\n```\n"
       "mybs.py = 지난 6주의 완성본 (제공). 오늘은 이 엔진으로 루프를 닫고,\n"
       "같은 모델을 정식 loopsym 으로 돌려 **6자리까지 같은 숫자**를 확인한다.\n"
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
    code("# ★브리지: 같은 문제를 정식 loopsym(전달함수 플랜트)으로\n"
         "import sys; sys.path.insert(0, '../..')\n"
         "import loopsym as bs\n"
         "bd2 = bs.Diagram()\n"
         "ref = bd2.add(bs.Step(t_on=1.0)); err = bd2.add(bs.Sum('+-'))\n"
         "kp = bd2.add(bs.Gain(3.0)); it = bd2.add(bs.Integrator()); ki = bd2.add(bs.Gain(2.0))\n"
         "pi = bd2.add(bs.Sum('++')); plant = bd2.add(bs.TransferFunction([1],[1,2,1]))\n"
         "sc2 = bd2.add(bs.Scope(n_in=1))\n"
         "bd2.connect(ref, err[0]); bd2.connect(plant, err[1]); bd2.connect(err, kp)\n"
         "bd2.connect(err, it); bd2.connect(it, ki); bd2.connect(kp, pi[0]); bd2.connect(ki, pi[1])\n"
         "bd2.connect(pi, plant); bd2.connect(plant, sc2)\n"
         "bs.run(bd2, 10.0, 0.01)\n"
         "print('loopsym y(10s) =', f'{sc2.data[0][-1]:.6f}')\n"
         "print('최대차 =', max(abs(a-b) for a,b in zip(sc.data[0], sc2.data[0])))"),
    md("## 과제\n"
       "1. `build_pi_loop` — 위 그림대로 (채점: 기준값 + loopsym 전 구간 대조)\n"
       "2. `build_pendulum` — 비선형 진자 + PD (ex2). θ 가 0.8 에 못 가는 이유를\n"
       "   한 문단으로 쓰라 (가산점: I 를 추가해 오차를 없애 보라)\n\n"
       "**다음 주 예고**: 이제 정식 플랫폼으로 갈아탄다 — 8주차, 6-DoF 쿼드로터가\n"
       "팔레트에서 기다린다. 학기 초의 그 그림이 학기 말에 진짜 기체를 난다."),
    GRADE(7),
]


# ================================================================
# 후반부 (8~15주차) — 팔레트 개방 트랙. 과제 = 모델 JSON 제출
# (뷰어에서 완성 → 저장으로 weekNN_model.json 덮어쓰기 → 채점).
# 모델 뼈대/정답의 정본은 tools/gen_week_models.py.
# ================================================================

VIEWER = lambda n: code(
    f"# 뷰어 열기 — 뼈대 모델을 브라우저에서 편집한다.\n"
    f"# 완성하면 뷰어의 '저장' → week{n:02d}_model.json 이 다운로드된다.\n"
    f"# 그 파일을 이 폴더의 같은 이름 파일에 **덮어쓰면 제출 완료** (채점 셀로 확인).\n"
    f"import sys, webbrowser; sys.path.insert(0, '../..')\n"
    f"from loopsym import load_json, render_html\n"
    f"p = render_html(load_json('week{n:02d}_model.json'), 'week{n:02d}_viewer.html',\n"
    f"                title='{n}주차', t_end=8.0, dt=0.004,\n"
    f"                save_name='week{n:02d}_model.json')\n"
    f"webbrowser.open('file://' + p)")

RUNCHK = lambda n, T: code(
    f"# 노트북에서 바로 실행해 보기 (뷰어 없이) — 저장한 모델을 로드해 시뮬\n"
    f"import sys; sys.path.insert(0, '../..')\n"
    f"from loopsym import load_json, Simulator\n"
    f"bd = load_json('week{n:02d}_model.json')\n"
    f"sim = Simulator(bd); sim.run({T}, 0.004)\n"
    f"import matplotlib.pyplot as plt\n"
    f"for b in sim.bd.blocks:\n"
    f"    if type(b).__name__ == 'Scope':\n"
    f"        plt.figure(figsize=(8,2.6)); plt.title(b.name); plt.grid(True)\n"
    f"        for i, lab in enumerate(b.labels): plt.plot(b.t, b.data[i], label=lab)\n"
    f"        plt.legend()")

CHAIN = ("```\n[Sensors] → [Estimation] → [Navigation] → [Control] → [Allocation] → [Plant]\n"
         "{arrow}\n```\n")


def chain(mark):
    """신호사슬에서 이번 주에 열리는 팔레트 위치 표시."""
    pos = {"Sensors": 1, "Estimation": 14, "Navigation": 29, "Control": 44,
           "Allocation": 56, "Plant": 71}[mark]
    return CHAIN.format(arrow=" " * pos + "▲ 이번 주")


NB[8] = [
    md("# 8주차 — Plant 팔레트: 6-DoF 쿼드로터\n\n"
       "**후반부 시작.** 지금까지는 엔진을 만들었다 — 이제 정식 loopsym 의\n"
       "팔레트를 신호사슬 순서로 하나씩 연다. 학기 초에 그린 다이어그램이\n"
       "학기 말(실기체)까지 같은 그림이다.\n\n" + chain("Plant") +
       "\n목표: 13-상태 강체 동역학의 구조. **개루프 불안정 체험.**"),
    md("## 이론 요약\n"
       "- 상태 13개: 쿼터니언 q(4) + 각속도 ω(3) + 위치 NED(3) + 속도(3)\n"
       "- 왜 쿼터니언인가: 오일러각은 ±90° 특이점 (짐벌락)\n"
       "- 추력: 모터 4개가 body −z 로 민다. 토크: 모터 위치×추력 + 반작용(요)\n"
       "- **개루프 = 제어 없음**: 쿼드로터는 자체 안정성이 없다 — 손을 놓으면 뒤집힌다\n"
       "- fidelity 개념 (ARCHITECTURE §2): 오늘 이 블록의 드롭다운이 학기 말에\n"
       "  Gazebo/실기체가 된다. **다이어그램은 하나.**"),
    VIEWER(8),
    md("## 실습 — 호버 추력 손 계산\n"
       "★hover_cmd 상수가 0.0 이라 기체가 자유낙하한다. 힘 평형 `m·g = N·k_F·u`\n"
       "에서 u 를 계산하라 (m=1kg, g=9.81, N=4, k_F=m·g/2 — QuadPlant 기본값).\n"
       "뷰어에서 ★hover_cmd 더블클릭 → value 수정 → 실행 → 고도 유지 확인 → 저장."),
    RUNCHK(8, 3.0),
    md("## 과제\n"
       "1. week08_model.json 완성 (채점기: 3초 뒤 고도 유지)\n"
       "2. 리포트: u 를 ±2% 만 틀리면 몇 초 만에 1m 를 벗어나는가? 실험으로 확인하고\n"
       "   '개루프는 왜 실용이 안 되는가' 를 한 문단으로."),
    GRADE(8),
]

NB[9] = [
    md("# 9주차 — Control I: 샘플링과 Rate 제어\n\n" + chain("Control") +
       "\n목표: 실제 컨트롤러는 **주기 프로그램**(이산 시간)이다. 각속도(rate) PID.\n"
       "PX4 의 가장 안쪽 루프 — 이번 주 블록은 PX4 v1.16 rate_control.cpp 이식본이다."),
    md("## 이론 요약\n"
       "- sample_time / ZOH / z⁻¹: 6주차에 만든 이산 블록이 실전에 등장\n"
       "- 캐스케이드의 안쪽부터: rate 루프가 가장 빠르다 (PX4 250Hz~1kHz)\n"
       "- RateController 내부: P + I(anti-windup) + D(필터링 미분) — ex9 화이트박스로\n"
       "  더블클릭해 들어가 볼 수 있다\n"
       "- Ts 가 커지면? 위상 지연 → 성능 저하 → 불안정 (과제)"),
    VIEWER(9),
    md("## 실습 — rate 피드백 배선\n"
       "뼈대는 rate_ctrl 의 각속도 피드백 3줄이 비어 있다 (실행하면 '미연결' 에러가\n"
       "정확히 어디인지 알려준다). 플랜트의 p/q/r 출력 → rate_ctrl 의 p/q/r 입력.\n"
       "완성하면: 1초에 요 회전 0.5 rad/s 명령 → 기체가 제자리에서 돌기 시작한다."),
    RUNCHK(9, 4.0),
    md("## 과제\n"
       "1. week09_model.json 완성 (채점기: r 이 0.5 rad/s 추종)\n"
       "2. rate_ctrl 의 st 를 0.004→0.02→0.05 로 키우며 추종 파형 비교 리포트\n"
       "   (dt 는 0.004 유지 — st 는 dt 의 정수배).\n"
       "3. (심화) ex9 화이트박스에서 Rate_Yaw 안에 들어가 LPF(2Hz)의 역할을 설명하라."),
    GRADE(9),
]

NB[10] = [
    md("# 10주차 — Control II + Allocation: 호버 폐루프 완성\n\n" + chain("Allocation") +
       "\n**드론이 처음 뜨는 주.** 캐스케이드(위치→자세→각속도)와 믹서를 잇는다."),
    md("## 이론 요약\n"
       "- 캐스케이드가 계층인 이유: 바깥 루프는 안쪽 루프의 setpoint 를 만든다\n"
       "  (위치 오차 → 가속도 → **자세**·추력 → 각속도 → 토크)\n"
       "- 쿼터니언 자세오차(개념): '지금 자세에서 목표 자세로 가는 최단 회전'\n"
       "- Allocation(믹서): 정규화 토크/추력 → 모터 4개. **제어기는 기체를 모른다** —\n"
       "  기체 차이는 믹서가 흡수 (PX4 구조. 14주차에 이 말의 의미를 확인한다)\n"
       "- Mixer 블록의 frame 파라미터: quad_x/quad_plus/hexa_x/octo_x"),
    VIEWER(10),
    md("## 실습 — 캐스케이드 잇기\n"
       "뼈대에서 빠진 것: ①pos_ctrl 출력(roll/pitch/yaw_cmd)→att_ctrl 의 att_cmd,\n"
       "②att_ctrl 출력(rate_sp)→rate_ctrl, ③pos_ctrl 의 thrust→mixer.\n"
       "포트에 마우스를 올리면 이름이 뜬다. 완성하면: 북 2m + 고도 6m 이동 후 정지 호버."),
    RUNCHK(10, 8.0),
    md("## 과제 (팀 프로젝트 시작)\n"
       "1. week10_model.json 완성 (채점기: 최종 NED=[2,0,−6] ±0.1m + 정착)\n"
       "2. north_sp 의 Step 높이를 5m 로 키우고 오버슈트를 관찰 — 어느 게인을\n"
       "   만지면 줄어드는가? (튜닝 근거를 남겨라 — 15주차 발표 재료)"),
    GRADE(10),
]

NB[11] = [
    md("# 11주차 — Sensors 팔레트: ideal → noisy 의 순간 ★\n\n" + chain("Sensors") +
       "\n목표: **완벽한 센서라는 거짓말.** 지금까지 제어기는 플랜트의 참값을 읽었다.\n"
       "실제 기체에는 참값이 없다 — IMU 가 있을 뿐이다."),
    md("## 이론 요약\n"
       "- IMU = 자이로(각속도) + 가속도계(비력). 레벨 정지에서 가속도계는 [0,0,−g]\n"
       "- 노이즈 모델 (ICM-42688 급 datasheet): bias + 백색잡음(noise density ×\n"
       "  √대역폭) + 샘플레이트 제한\n"
       "- **fidelity 규약** (ARCHITECTURE §2): ideal ↔ noisy ↔ gazebo ↔ hardware —\n"
       "  포트는 절대 불변. 다이어그램은 하나.\n"
       "- 시드 고정: 채점/회귀 재현성 (같은 seed = 같은 잡음열)"),
    VIEWER(11),
    md("## 실습 — 이 한 번의 클릭\n"
       "① 10주차 다이어그램에 IMU 블록 삽입: 플랜트 q/ω/vel → IMU 입력,\n"
       "   rate_ctrl 의 각속도 피드백을 참값 대신 **IMU gyro 출력**으로 재배선.\n"
       "② IMU 더블클릭 → fidelity 를 `ideal` → `noisy` 로. **기체가 흔들리기\n"
       "   시작하는 것을 목격하라.** 이 클릭이 상태추정이라는 분야가 존재하는 이유다.\n"
       "   (gyro_bias=0.02, gyro_nd=1e-3 으로 설정 — 채점 기준)"),
    RUNCHK(11, 8.0),
    md("## 과제\n"
       "1. week11_model.json 완성 (채점기: IMU 구조 + noisy + 미션 유지)\n"
       "2. 경계 리포트: gyro_nd 를 1e-3 → 1e-2 → 5e-2 로 키우며 어느 수준부터\n"
       "   미션이 실패하는지 경계를 찾아라 (seed 고정 후 스윕)."),
    GRADE(11),
]

NB[12] = [
    md("# 12주차 — Estimation 팔레트: 필터로 복구\n\n" + chain("Estimation") +
       "\n목표: 상보필터(Mahony)의 원리 — 자이로 적분(고주파) + 가속도계 보정(저주파)\n"
       "+ **바이어스 추정**. 11주차의 흔들림 중 '바이어스' 성분을 걷어낸다."),
    md("## 이론 요약\n"
       "- 자이로만: 적분 드리프트 (바이어스가 각도로 쌓인다)\n"
       "- 가속도계만: 기동/진동에 떨린다 (비력 ≠ 중력)\n"
       "- 융합: ω_corr = gyro − b̂ + Kp·e,  b̂˙ = −Ki·e,  e = 측정중력 × 추정중력\n"
       "- **정직한 한계 (중요)**: 추력만 받는 기체는 기울면 수평가속하며 비력이 항상\n"
       "  body−z — 가속 중 tilt 관측 불가. CF 자세추정을 제어 자세 피드백에 그대로\n"
       "  쓰면 발산한다! 그래서 이번 주는 **바이어스 보정 각속도(omega_est)만** 쓴다.\n"
       "  자세까지 추정으로 날려면 GPS 속도 결합(EKF2)이 필요 — MATLAB 라인 T1 수업\n"
       "  의 예고편이다 (px4_controller/nav/EKF2_gravity_notes 참조)."),
    VIEWER(12),
    md("## 실습 — CF 삽입\n"
       "① ComplementaryFilter 블록 삽입: IMU 의 gyro+accel 6줄 → CF 입력.\n"
       "② rate_ctrl 의 각속도 피드백을 IMU gyro → **CF 의 p/q/r (omega_est)** 로 재배선.\n"
       "③ 실행 — 11주차 대비 바이어스로 인한 자세 오프셋이 사라지는 것을 확인."),
    RUNCHK(12, 8.0),
    md("## 과제\n"
       "1. week12_model.json 완성 (채점기: CF 구조 + 미션 + 'CF→자세 직결 금지')\n"
       "2. 트레이드오프 리포트: CF 의 ki 를 0.05→0.5 로 키우면 바이어스 수렴은\n"
       "   빨라지지만 무엇이 나빠지는가? (힌트: 진동 전달)"),
    GRADE(12),
]

NB[13] = [
    md("# 13주차 — Navigation: 미션을 시키는 법 + 실시간 모드\n\n" + chain("Navigation") +
       "\n목표: 웨이포인트 순회(미션 계층) + 시뮬 시간 vs 벽시계 시간."),
    md("## 이론 요약\n"
       "- 항법 계층은 위치 setpoint 를 만든다 — 유도(오차→속도명령)는 아래의\n"
       "  위치 캐스케이드가 이미 하고 있다\n"
       "- WaypointManager: 반경 안에 들어오면 다음 지점 (waypoints=\"N,E,D; ...\")\n"
       "- 실시간 모드: 배치 시뮬(수십 ms)과 수치는 같지만 벽시계에 페이싱 —\n"
       "  실기체/ROS2 로 가는 전제 (P42)\n"
       "- ROS2 데모 (ex6): 같은 다이어그램 구조가 실제 미들웨어의 노드가 된다"),
    VIEWER(13),
    md("## 실습 — 미션 배선\n"
       "뼈대는 hold 상수가 제자리 호버를 시키고 있다. ★wp_manager 를 살려라:\n"
       "① 플랜트 위치(pN/pE/pD) → wp 입력, ② wp 의 n_sp/e_sp/d_sp → pos_ctrl.\n"
       "완성하면: [2,0,−6] → [2,2,−6] → [0,0,−5] 순회 후 마지막 지점 호버.\n"
       "scope_wp 의 wp_idx 가 계단처럼 0→1→2→3 오르는 것을 확인."),
    RUNCHK(13, 16.0),
    md("## 실시간 모드 / ROS2 데모 (수업 시연)\n"
       "```bash\n"
       "# 터미널 1 — 로컬 서버 모드\npython -m loopsym.server\n"
       "# 뷰어 새로고침 → 배지가 'Local Server' → '실시간' 체크 → 실행\n"
       "# Scope 가 벽시계 속도로 차오른다 (external mode)\n\n"
       "# ROS2 turtlesim (환경 있는 경우): examples/ex6_ros2_turtlesim.py 참조\n```"),
    md("## 과제 (팀)\n"
       "1. week13_model.json 완성 (채점기: 전 웨이포인트 방문 + 복귀)\n"
       "2. 자기 미션 설계: 웨이포인트 4개 이상 + radius 튜닝 — 반경이 너무 작으면/크면\n"
       "   무슨 일이 생기는지 리포트."),
    GRADE(13),
]

NB[14] = [
    md("# 14주차 — Interfaces: 플랜트를 진짜로 바꾼다\n\n" + chain("Plant") +
       "\n목표: **\"같은 다이어그램, 다른 기체.\"** fidelity 사다리의 의미를 체험한다."),
    md("## 이론 요약\n"
       "- fidelity Level 2/3: plant/센서 블록의 출력을 Gazebo 토픽/MAVLink 로 교체 —\n"
       "  다이어그램상으로는 여전히 같은 블록 (ARCHITECTURE §2)\n"
       "- SITL/브리지/시간 동기 개념 (MATLAB 라인의 run_px4_sitl_bridge 가 실물 예)\n"
       "- 이번 주 실습은 소프트웨어판: **기체 파라미터를 바꿔도 미션이 완주되는가** —\n"
       "  채점기가 여러분의 다이어그램에서 기체 질량을 +30% 로 바꿔서 돌린다.\n"
       "  제어기·믹서 구조는 그대로 (10주차 '제어기는 기체를 모른다'의 증명)"),
    VIEWER(14),
    md("## 실습\n"
       "① 13주차 미션 모델을 그대로 가져온다 (뼈대 = 13주차와 동일 출발).\n"
       "② 뷰어에서 QuadPlant 의 m 을 1.3 으로 바꿔 직접 실행해 보라 — 처음엔 고도가\n"
       "   처지다가 위치 적분기가 추력을 끌어올리는 과정을 Scope 로 관찰.\n"
       "③ m 을 1.0 으로 되돌리고 저장 — 채점기가 알아서 1.3 으로 바꿔 검사한다.\n"
       "④ (데모) Mixer/QuadPlant 의 frame 을 hexa_x 로 — 로터 6개 기체도 같은\n"
       "   제어기로 난다 (포트 수가 바뀌므로 모터 배선 2줄 추가)."),
    RUNCHK(14, 16.0),
    md("## 과제 (팀)\n"
       "1. week14_model.json 완성 (채점기: 원기체 + 무거운 기체 양쪽 완주)\n"
       "2. 종합 프로젝트 마무리: 15주차 발표 준비 — 다이어그램 화면 + 파형 + 튜닝 근거."),
    GRADE(14),
]

NB[15] = [
    md("# 15주차 — 종합 프로젝트: 발표와 자동 채점\n\n"
       "```\n[Sensors] → [Estimation] → [Navigation] → [Control] → [Allocation] → [Plant]\n"
       "   ▲───────────── 전부 열렸다: 신호사슬을 완성하라 ─────────────▲\n```\n"
       "학기 초 1주차의 `step(t)` 가 여기까지 왔다."),
    md("## 자동 채점분 (프로젝트 점수의 40%)\n"
       "week15_model.json = **풀 체인 미션**: noisy IMU + ComplementaryFilter +\n"
       "WaypointManager 순회. 12주차와 13주차를 한 다이어그램에 합치면 된다.\n\n"
       "## 발표 (20%)\n"
       "다이어그램 화면 공유 + ① 신호사슬 설명 ② 파형 해설(왜 이렇게 움직이는가)\n"
       "③ 튜닝 근거 (무엇을 바꿨고 왜).\n\n"
       "## 데모 — fidelity Level 3 예고\n"
       "강사 시연: 같은 다이어그램이 실기체/HILS 로 (P41/P43 — 심화 과정).\n"
       "\"학기 초의 그 그림이 진짜 기체를 난다.\""),
    VIEWER(15),
    RUNCHK(15, 20.0),
    GRADE(15),
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
