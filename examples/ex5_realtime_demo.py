"""예제 5 — 실시간 모드 [CLD-P42]: P40 데모를 뷰어에서 라이브로.

P40 스파이크의 워크로드(이산 PI 폐루프, 50Hz)를 실시간 모드로 돌린다.
sim 모드는 10초 시뮬레이션이 수십 ms 에 끝나지만, 실시간 모드는 벽시계
10초에 맞춰 진행된다 — Scope 가 "차오르는" 것이 눈에 보인다.
실기체(Bebop/ROS2/MAVLink 블록)는 전부 이 모드 위에 얹힌다.

뷰어에서 라이브로 보기:
  1. 터미널 1:  python -m blocksim.server
  2. 이 스크립트 실행 → ex5_diagram.html 생성
  3. 브라우저로 열기 → 좌상단 배지가 "Local Server" 인지 확인
  4. "실시간" 체크 → ▶ 실행 → Scope 가 벽시계 속도로 라이브 갱신,
     완료 시 상태줄에 지터 통계(p99/miss)가 표시된다. ■ 정지 가능.

이 스크립트 자체는 헤드리스로 3초를 실시간 실행해 지터 통계를 출력한다.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blocksim import (
    Diagram, Step, Sum, Gain, DiscreteIntegrator, TransferFunction, Scope,
    run_realtime, render_html,
)

TS = 0.02        # 50Hz — P40 스파이크와 동일


def build():
    bd = Diagram()
    ref = bd.add(Step(t_on=1.0, name="ref"))
    err = bd.add(Sum("+-", name="err"))
    kp = bd.add(Gain(3.0, name="Kp"))
    integ = bd.add(DiscreteIntegrator(st=TS, name="dint"))
    ki = bd.add(Gain(2.0, name="Ki"))
    add = bd.add(Sum("++", name="PI"))
    plant = bd.add(TransferFunction([1], [1, 2, 1], name="plant"))
    sc = bd.add(Scope(n_in=2, labels=["ref", "y"], name="scope"))
    bd.connect(ref, err[0]); bd.connect(plant, err[1])
    bd.connect(err, kp); bd.connect(err, integ); bd.connect(integ, ki)
    bd.connect(kp, add[0]); bd.connect(ki, add[1]); bd.connect(add, plant)
    bd.connect(ref, sc[0]); bd.connect(plant, sc[1])
    return bd, sc


if __name__ == "__main__":
    bd, sc = build()
    print("html :", render_html(
        bd, os.path.join(os.path.dirname(__file__), "ex5_diagram.html"),
        title="ex5 — realtime PI (서버 켜고 '실시간' 체크)"))

    print(f"헤드리스 실시간 실행 3초 @ {1/TS:.0f}Hz …")
    stats = run_realtime(bd, t_end=3.0, dt=TS)
    print(f"경과 {stats['elapsed_s']:.2f}s (벽시계 3초에 맞춰 돌았는지 확인)")
    print(f"지터: p50 {stats['p50']:.3f}  p95 {stats['p95']:.3f}  "
          f"p99 {stats['p99']:.3f}  max {stats['max']:.3f} ms | "
          f"miss {stats['miss_pct']:.2f}%  (주기 {stats['period_ms']:.0f}ms)")
    print(f"y(3s) = {sc.data[1][-1]:.6f}  — sim 모드와 동일한 수치여야 함")
