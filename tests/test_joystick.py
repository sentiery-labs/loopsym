"""Joystick 블록 — 매핑/데드존/모드 래치/중립 폴백."""

import math

from loopsym import Constant, Diagram, Joystick, PyFunction, Scope, Simulator, QuadPlant

DT = 0.004


def test_neutral_without_input():
    """입력 미연결(배치/Pyodide) = 중립 스틱 + idle_thrust — 재현 가능."""
    j = Joystick(idle_thrust=0.5)
    assert j.output(0, (), j.dinitial()) == (0.0, 0.0, 0.0, 0.5, 0.0)


def test_axis_mapping_rc_mode2():
    j = Joystick(deadzone=0.05)
    live = {"axes": [0.3, -1.0, 0.5, -0.4], "buttons": []}
    j.attach(live)
    roll, pitch, yaw, thrust, mode = j.output(0, (), j.dinitial())
    assert yaw == 0.3                      # 왼스틱 좌우
    assert thrust == 1.0                   # 왼스틱 위로 끝까지 (axes[1]=-1)
    assert roll == 0.5                     # 오른스틱 좌우
    assert pitch == 0.4                    # 오른스틱 위 = +
    live["axes"] = [0.02, 0.0, -0.01, 0.0]  # 데드존 이내
    assert j.output(0, (), j.dinitial())[0:3] == (0.0, 0.0, 0.0)


def test_mode_latch():
    j = Joystick(mode_btns="0,1", st=DT)
    live = {"axes": [0, 0, 0, 0], "buttons": [0, 0]}
    j.attach(live)
    xd = j.dinitial()
    xd = j.update(0, (), xd)
    assert xd[0] == 0.0                    # 아무것도 안 눌림
    live["buttons"] = [1, 0]
    xd = j.update(0, (), xd)
    assert xd[0] == 1.0                    # 버튼0 → 모드1
    live["buttons"] = [0, 0]
    xd = j.update(0, (), xd)
    assert xd[0] == 1.0                    # 래치 유지
    live["buttons"] = [0, 1]
    xd = j.update(0, (), xd)
    assert xd[0] == 2.0                    # 버튼1 → 모드2


def test_in_diagram_live_update():
    """다이어그램 안에서 attach 된 라이브 값이 출력으로 흐른다."""
    bd = Diagram()
    joy = bd.add(Joystick(st=DT))
    sc = bd.add(Scope(n_in=2, labels=["roll", "thrust"]))
    bd.connect(joy[0], sc[0])
    bd.connect(joy[3], sc[1])
    live = {"axes": [0.0, -0.5, 0.6, 0.0], "buttons": []}
    joy.attach(live)
    Simulator(bd).run(0.1, DT)
    assert sc.data[0][-1] == 0.6 and sc.data[1][-1] == 0.75
    assert all(math.isfinite(v) for ch in sc.data for v in ch)
