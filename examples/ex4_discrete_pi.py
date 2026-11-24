"""예제 4 — 연속 PI vs 이산 PI (PX4 로 가는 다리).

실제 비행 컨트롤러(PX4)는 연속 적분기가 아니라 일정 주기(sample_time)로
도는 이산 제어기다. 같은 게인의 PI 를 연속/이산 두 벌로 만들어 비교한다.

이산판은 오차 신호에 ZeroOrderHold 를 단다 — FC 가 Ts 마다 센서를 읽고,
계산한 출력을 다음 주기까지 붙잡는 것과 같다. 그래서 I 항뿐 아니라 P 항도
샘플 시점 값으로만 계산되는 진짜 디지털 PI 가 된다. (ZOH 없이 적분기만
이산으로 바꾸면 P 항은 연속으로 남아 샘플링 영향이 작게 보인다.)

관찰 포인트 (y 최대값, 연속 PI 는 약 1.24):
  · Ts=0.01 이면 연속과 거의 겹친다 (빠른 샘플링 ≈ 연속)
  · Ts=0.3 → 약 1.41, Ts=0.5 → 약 1.52 : 샘플·유지 지연으로 오버슈트 증가
  · Ts=1.0 → 약 1.78 에 진동이 오래 남는다 — 더 키우면 불안정.
    "샘플링 주기가 제어 성능의 일부"라는 것이 이산 제어 수업의 출발점.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from loopsym import (
    Diagram, Step, Sum, Gain, Integrator, DiscreteIntegrator, ZeroOrderHold,
    TransferFunction, Scope, run, render_html,
)

KP, KI = 3.0, 2.0
TS = 0.1        # 이산 제어기 샘플 주기 — 0.01/0.3/0.5/1.0 으로 바꿔 볼 것


def pi_loop(discrete):
    bd = Diagram()
    ref = bd.add(Step(t_on=1.0, name="ref"))
    err = bd.add(Sum("+-", name="err"))
    e = err
    if discrete:            # FC 의 센서 읽기: 오차를 Ts 마다 샘플해 붙잡는다
        e = bd.add(ZeroOrderHold(st=TS, name="sample"))
        bd.connect(err, e)
    kp = bd.add(Gain(KP, name="Kp"))
    integ = bd.add(DiscreteIntegrator(st=TS, name="dint") if discrete
                   else Integrator(name="int"))
    ki = bd.add(Gain(KI, name="Ki"))
    add = bd.add(Sum("++", name="PI"))
    plant = bd.add(TransferFunction([1], [1, 2, 1], name="plant"))
    sc = bd.add(Scope(n_in=1, labels=["y"], name="scope"))
    bd.connect(ref, err[0]); bd.connect(plant, err[1])
    bd.connect(e, kp); bd.connect(e, integ); bd.connect(integ, ki)
    bd.connect(kp, add[0]); bd.connect(ki, add[1]); bd.connect(add, plant)
    bd.connect(plant, sc)
    return bd, sc


bd_c, sc_c = pi_loop(discrete=False)
bd_d, sc_d = pi_loop(discrete=True)
run(bd_c, 10.0, 0.01)
run(bd_d, 10.0, 0.01)

plt.figure(figsize=(8, 4))
plt.plot(sc_c.t, sc_c.data[0], label="continuous PI")
plt.plot(sc_d.t, sc_d.data[0], label=f"discrete PI (Ts={TS})", linestyle="--")
plt.xlabel("time [s]"); plt.legend(); plt.grid(True)
plt.title("Continuous vs Discrete PI — loopsym")
out = os.path.join(os.path.dirname(__file__), "ex4_result.png")
plt.savefig(out, dpi=110, bbox_inches="tight")
print("plot :", out)
print("html :", render_html(bd_d, os.path.join(os.path.dirname(__file__), "ex4_diagram.html"),
                            title="ex4 — discrete PI"))
print(f"연속 y(10s) = {sc_c.data[0][-1]:.6f} / 이산(Ts={TS}) y(10s) = {sc_d.data[0][-1]:.6f}")
