"""예제 10 — 조이스틱 수동 비행 + 모드 전환 (Joystick 블록).

RC 조종기처럼 게임패드로 기체를 직접 조종한다:
  오른스틱 = roll/pitch (자세 명령, 최대 ±28°),  왼스틱 = thrust/yaw
  버튼 A(0) = 수동 자세 모드,  버튼 B(1) = 위치유지(Position Hold) 모드

mode_mux(PyFunction) 가 Joystick 의 mode 채널로 두 명령원을 전환한다:
  mode 0/1 (수동)  : att_cmd ← 스틱,  thrust ← 스틱
  mode 2 (포지션홀드): att_cmd/thrust ← PositionController (현 위치 [0,0,-5] 유지)

실행 (라이브 조종은 서버 모드 + 실시간):
  1. 게임패드 USB 연결
  2. 터미널 1:  python -m loopsym.server
  3. python examples/ex10_joystick_fly.py  →  뷰어 열림 (배지 'Local Server' 확인)
  4. t_end 를 넉넉히(60), '실시간' 체크 → ▶ 실행 → 스틱으로 조종!
     (Scope 팝업 창을 열어두면 관제 화면처럼 쓸 수 있다)

이 스크립트 자체는 헤드리스 검증: 입력 없음 = 중립 스틱 → 레벨 호버 유지.
"""

import math
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loopsym import (
    Constant, Diagram, Joystick, PyFunction, Scope, Simulator, render_html,
    QuadPlant, PositionController, AttitudeController, RateController, Mixer,
)

DT = 0.004
TILT_MAX = 28 * math.pi / 180      # 스틱 풀 = ±28° (MPC_TILTMAX 근방)


def build():
    bd = Diagram()
    plant = bd.add(QuadPlant(z0=-5.0, name="quad"))
    joy = bd.add(Joystick(st=DT, name="joystick"))
    pos = bd.add(PositionController(st=DT, name="pos_hold"))
    att = bd.add(AttitudeController(name="att_ctrl"))
    rate = bd.add(RateController(st=DT, name="rate_ctrl"))
    mix = bd.add(Mixer(name="mixer"))

    # 위치유지 명령원: 현 위치 [0,0,-5] 유지
    zero = bd.add(Constant(0.0, name="hold_ne"))
    hold_d = bd.add(Constant(-5.0, name="hold_d"))
    bd.connect(zero, pos[0]); bd.connect(zero, pos[1]); bd.connect(hold_d, pos[2])
    bd.connect(zero, pos[3])
    for i in range(3):
        bd.connect(plant[7 + i], pos[4 + i])
        bd.connect(plant[10 + i], pos[7 + i])

    # 모드 먹스: 수동(스틱) ↔ 포지션홀드(PositionController)
    mux = bd.add(PyFunction("\n".join([
        "# u0=mode | 수동: u1=roll_stick u2=pitch_stick u3=thrust_stick",
        "#          | 홀드: u4=roll_cmd u5=pitch_cmd u6=thrust",
        f"manual = u0 < 1.5",
        f"y0 = u1 * {TILT_MAX} if manual else u4",
        f"y1 = u2 * {TILT_MAX} if manual else u5",
        "y2 = u3 if manual else u6",
    ]), n_in=7, n_out=3, name="mode_mux"))
    bd.connect(joy[4], mux[0])                    # mode
    bd.connect(joy[0], mux[1]); bd.connect(joy[1], mux[2]); bd.connect(joy[3], mux[3])
    bd.connect(pos[0], mux[4]); bd.connect(pos[1], mux[5]); bd.connect(pos[3], mux[6])

    yaw_cmd = bd.add(Constant(0.0, name="yaw_cmd"))
    for i in range(4):
        bd.connect(plant[i], att[i])
    bd.connect(mux[0], att[4]); bd.connect(mux[1], att[5]); bd.connect(yaw_cmd, att[6])
    for i in range(3):
        bd.connect(att[i], rate[i])
        bd.connect(plant[4 + i], rate[3 + i])
        bd.connect(rate[i], mix[i])
    bd.connect(mux[2], mix[3])                    # thrust
    for i in range(4):
        bd.connect(mix[i], plant[i])

    sc = bd.add(Scope(n_in=4, labels=["N", "E", "D", "mode"], name="scope"))
    for i in range(3):
        bd.connect(plant[7 + i], sc[i])
    bd.connect(joy[4], sc[3])
    return bd, sc


if __name__ == "__main__":
    bd, sc = build()
    Simulator(bd).run(3.0, DT)                    # 헤드리스: 중립 스틱 = 레벨 호버
    n, e, d, mode = (ch[-1] for ch in sc.data)
    print(f"중립 스틱 3s: NED=[{n:.3f},{e:.3f},{d:.3f}] mode={mode:.0f} (호버 유지)")
    assert abs(d + 5.0) < 0.2 and mode == 0
    here = os.path.dirname(os.path.abspath(__file__))
    out = render_html(bd, os.path.join(here, "ex10_diagram.html"),
                      title="ex10 — 조이스틱 비행", t_end=60.0, dt=DT)
    print("뷰어:", out, " (서버 모드 + 실시간 체크 + 게임패드)")
