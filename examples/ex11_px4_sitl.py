"""예제 11 — 진짜 PX4 펌웨어가 loopsym plant 를 비행 (MavlinkHil, CLD-P41).

fidelity Level 3 의 1단계: 다이어그램의 '제어기 자리'에 실제 PX4 v1.16
(EKF2 + commander + 제어기 전부)이 들어간다. 기체 없이 SITL 로 전체
파이프라인(센서 합성 → 펌웨어 → 액추에이터)을 검증한다.

    QuadPlant(ground) ─ 상태 13 ─▶ MavlinkHil ─▶ PX4 SITL (TCP 4560, lockstep)
              ▲                        │
              └──── 모터 u1..u4 ◀──────┘   + 가상 GCS(UDP 18570): arm+takeoff

요구: ~/PX4-Autopilot 빌드(px4_sitl_default) + pip install "loopsym[mavlink]"
실행: python examples/ex11_px4_sitl.py    (~60s 시뮬, lockstep 이라 벽시계도 비슷)
판정(MATLAB run_px4_sitl_bridge 와 동일): 말기 5s 고도 1.5~4.0m (MIS_TAKEOFF_ALT
2.5m 호버), 자세 |roll/pitch|<20°, actuator 링크 >90%.
"""

import math
import time
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loopsym import Diagram, MavlinkHil, QuadPlant, Scope, Simulator, render_html

DT = 0.004
DUR = 60.0


def build():
    bd = Diagram()
    plant = bd.add(QuadPlant(z0=0.0, ground=True, name="quad"))
    hil = bd.add(MavlinkHil(st=DT, takeoff_at=20.0, name="px4_sitl"))
    for i in range(13):
        bd.connect(plant[i], hil[i])          # 상태 13 → HIL 센서 합성
    for i in range(4):
        bd.connect(hil[i], plant[i])          # 실펌웨어의 모터 명령
    sc = bd.add(Scope(n_in=3, labels=["alt", "qx", "u1"], name="scope"))
    bd.connect(plant[9], sc[0])               # pD (아래 +)
    bd.connect(plant[1], sc[1])
    bd.connect(hil[0], sc[2])
    return bd, sc


if __name__ == "__main__":
    bd, sc = build()
    hil = next(b for b in bd.blocks if isinstance(b, MavlinkHil))
    print(f"[ex11] {DUR:.0f}s lockstep (250Hz) — t=20s arm+takeoff …")
    t_wall = time.monotonic()
    Simulator(bd).run(DUR, DT)
    wall = time.monotonic() - t_wall

    tail = int(5.0 / DT)
    alt = [-v for v in sc.data[0][-tail:]]
    alt_mean = sum(alt) / len(alt)
    alt_std = math.sqrt(sum((a - alt_mean) ** 2 for a in alt) / len(alt))
    qx_max = max(abs(v) for v in sc.data[1])
    ok_to = 1.5 < alt_mean < 4.0 and alt_std < 0.3
    ok_att = qx_max < math.sin(math.radians(20) / 2)
    ok_link = hil.link_ratio > 0.9
    print("\n===== PX4 SITL x loopsym plant (MavlinkHil) =====")
    print(f" lockstep 링크 : actuator {hil.link_ratio*100:.0f}% "
          f"{'PASS' if ok_link else 'FAIL'}")
    print(f" 이륙+고도유지 : 말기5s 평균 {alt_mean:.2f}m (std {alt_std:.2f}) "
          f"{'PASS' if ok_to else 'FAIL'}")
    print(f" 자세 안정     : |qx|max {qx_max:.3f} {'PASS' if ok_att else 'FAIL'}")
    print(f" 결과: {'PASS' if ok_to and ok_att and ok_link else 'FAIL'} — "
          "실제 PX4 v1.16 펌웨어가 loopsym plant 를 비행")
    print(f" {DUR:.0f}s 비행을 {wall:.1f}s 에 계산 (lockstep x{DUR/wall:.0f})")
    print("=================================================")
    here = os.path.dirname(os.path.abspath(__file__))
    print("뷰어:", render_html(bd, os.path.join(here, "ex11_diagram.html"),
                              title="ex11 — PX4 SITL HIL", t_end=DUR, dt=DT,
                              embed_scopes=True))
    sys.exit(0 if (ok_to and ok_att and ok_link) else 1)
