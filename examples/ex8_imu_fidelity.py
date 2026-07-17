"""예제 8 — 센서 fidelity [CLD-P62]: "다이어그램은 하나."

호버 폐루프의 rate 피드백을 IMU 블록으로 경유시킨다. 다이어그램은 같고
IMU 의 fidelity 파라미터만 ideal ↔ noisy 로 바꾼다 (ARCHITECTURE §2).
noisy 에서 자세 유지가 눈에 띄게 흔들린다 — 11주차 하이라이트(필터로
복구, P64 Complementary Filter)의 '문제 제시' 편.

실행:  python examples/ex8_imu_fidelity.py
  → fidelity 별 자세 RMS 비교 출력 + ex8_diagram.html 생성
    (뷰어에서 IMU 더블클릭 → fidelity 를 "noisy" 로 바꿔 재실행해 볼 것)
"""

import math
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loopsym import (
    Constant, Diagram, IMU, Scope, Simulator, render_html,
    QuadPlant, AttitudeController, RateController, QuadXMixer,
)

DT = 0.004
DEG = math.pi / 180.0


def build(fidelity):
    bd = Diagram()
    plant = bd.add(QuadPlant(roll0=10 * DEG, pitch0=-5 * DEG, z0=-5.0, name="quad"))
    imu = bd.add(IMU(fidelity=fidelity, gyro_nd=5e-3, st=DT, name="imu"))
    att = bd.add(AttitudeController(name="att_ctrl"))
    rate = bd.add(RateController(st=DT, name="rate_ctrl"))
    mix = bd.add(QuadXMixer(name="mixer"))
    zero = bd.add(Constant(0.0, name="level_cmd"))
    thr = bd.add(Constant(0.5, name="hover_thr"))
    for i in range(4):
        bd.connect(plant[i], imu[i])
        bd.connect(plant[i], att[i])
    for i in range(3):
        bd.connect(plant[4 + i], imu[4 + i])
        bd.connect(plant[10 + i], imu[7 + i])
        bd.connect(zero, att[4 + i])
        bd.connect(att[i], rate[i])
        bd.connect(imu[i], rate[3 + i])          # ★ rate 피드백 = IMU gyro
        bd.connect(rate[i], mix[i])
    bd.connect(thr, mix[3])
    for i in range(4):
        bd.connect(mix[i], plant[i])
    sc = bd.add(Scope(n_in=2, labels=["qx (자세)", "IMU gyro p"], name="scope"))
    bd.connect(plant[1], sc[0])
    bd.connect(imu[0], sc[1])
    return bd, sc


if __name__ == "__main__":
    for fid in ("ideal", "noisy"):
        bd, sc = build(fid)
        Simulator(bd).run(4.0, DT)
        half = len(sc.data[0]) // 2
        rms = math.sqrt(sum(v * v for v in sc.data[0][half:]) / half)
        print(f"fidelity={fid:6s}  정착 후 qx RMS = {rms:.2e}")
    here = os.path.dirname(os.path.abspath(__file__))
    bd, _ = build("ideal")
    out = render_html(bd, os.path.join(here, "ex8_diagram.html"),
                      title="ex8 — IMU fidelity (CLD-P62)")
    print("뷰어:", out, " (IMU 더블클릭 → fidelity=noisy 로 바꿔 재실행)")
