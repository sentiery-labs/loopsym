"""예제 7 — 드론 팔레트 [CLD-P65]: PX4 v1.16 위치제어 폐루프.

ARCHITECTURE §1 신호사슬을 블록 그대로 잇는다:
  PositionController → AttitudeController → RateController → QuadXMixer → QuadPlant
                                   ↑______________ 상태 피드백 ______________|

제어기는 px4_controller/ 의 소스 대조 검증본(PX4 v1.16)을 이식한 것.
시나리오 = Simulink 검증본 run_px4_pos_test_blocks 와 동일:
고도 5m 호버 시작 → 0.5s 에 북쪽 2m + 고도 6m 명령 → 이동 후 정지 호버.

실행:  python examples/ex7_drone_hover.py
  → 최종 위치 출력 + ex7_diagram.html 생성 (뷰어에서 편집/재실행 가능)
"""

import math
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loopsym import (
    Constant, Diagram, Scope, Simulator, Step, render_html,
    QuadPlant, PositionController, AttitudeController, RateController, QuadXMixer,
)

DT = 0.004       # PX4 자세루프 250Hz (px4_params.m)


def build():
    bd = Diagram()
    plant = bd.add(QuadPlant(z0=-5.0, name="quad"))
    pos = bd.add(PositionController(st=DT, name="pos_ctrl"))
    att = bd.add(AttitudeController(name="att_ctrl"))
    rate = bd.add(RateController(st=DT, name="rate_ctrl"))
    mix = bd.add(QuadXMixer(name="mixer"))

    # ---- 명령: 북 2m (0.5s 스텝) + 고도 6m + yaw 0 ----
    n_sp = bd.add(Step(t_on=0.5, height=2.0, name="north_sp"))
    e_sp = bd.add(Constant(0.0, name="east_sp"))
    d_sp = bd.add(Constant(-6.0, name="down_sp"))      # NED: 고도 6m = z −6
    yaw_sp = bd.add(Constant(0.0, name="yaw_sp"))
    for i, src in enumerate((n_sp, e_sp, d_sp, yaw_sp)):
        bd.connect(src, pos[i])

    # ---- 피드백: 플랜트 상태 -> 각 제어기 ----
    for i in range(3):
        bd.connect(plant[7 + i], pos[4 + i])    # pos N/E/D
        bd.connect(plant[10 + i], pos[7 + i])   # vel N/E/D
    for i in range(4):
        bd.connect(plant[i], att[i])            # q
    for i in range(3):
        bd.connect(pos[i], att[4 + i])          # att_cmd (roll/pitch/yaw)
        bd.connect(att[i], rate[i])             # rate_sp
        bd.connect(plant[4 + i], rate[3 + i])   # rate (p/q/r)
        bd.connect(rate[i], mix[i])             # torque
    bd.connect(pos[3], mix[3])                  # thrust_cmd
    for i in range(4):
        bd.connect(mix[i], plant[i])            # motors

    sc = bd.add(Scope(n_in=3, labels=["N [m]", "E [m]", "D [m]"], name="scope_pos"))
    for i in range(3):
        bd.connect(plant[7 + i], sc[i])
    return bd, sc


if __name__ == "__main__":
    bd, sc = build()
    Simulator(bd).run(8.0, DT)
    n, e, d = (ch[-1] for ch in sc.data)
    print(f"최종 위치 NED = [{n:.3f}, {e:.3f}, {d:.3f}]  (목표 [2, 0, -6])")
    assert abs(n - 2.0) < 0.1 and abs(e) < 0.1 and abs(d + 6.0) < 0.1
    here = os.path.dirname(os.path.abspath(__file__))
    out = render_html(bd, os.path.join(here, "ex7_diagram.html"),
                      title="ex7 — PX4 드론 위치제어 (CLD-P65)")
    print("뷰어:", out)
