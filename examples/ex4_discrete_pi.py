"""예제 4 — 연속 PI vs 이산 PI (PX4 로 가는 다리).

실제 비행 컨트롤러(PX4)는 연속 적분기가 아니라 일정 주기(sample_time)로
도는 이산 제어기다. 같은 게인의 PI 를 연속/이산 두 벌로 만들어 비교한다.

관찰 포인트:
  · Ts=0.01 이면 연속과 거의 겹친다 (빠른 샘플링 ≈ 연속)
  · Ts 를 0.2 로 키우면? → 위상 지연으로 오버슈트 증가, 더 키우면 불안정.
    "샘플링 주기가 제어 성능의 일부"라는 것이 이산 제어 수업의 출발점.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from loopsym import (
    Diagram, Step, Sum, Gain, Integrator, DiscreteIntegrator,
    TransferFunction, Scope, run, render_html,
)

KP, KI = 3.0, 2.0
TS = 0.1        # 이산 제어기 샘플 주기 — 0.01/0.1/0.2 로 바꿔 볼 것


def pi_loop(discrete):
    bd = Diagram()
    ref = bd.add(Step(t_on=1.0, name="ref"))
    err = bd.add(Sum("+-", name="err"))
    kp = bd.add(Gain(KP, name="Kp"))
    integ = bd.add(DiscreteIntegrator(st=TS, name="dint") if discrete
                   else Integrator(name="int"))
    ki = bd.add(Gain(KI, name="Ki"))
    add = bd.add(Sum("++", name="PI"))
    plant = bd.add(TransferFunction([1], [1, 2, 1], name="plant"))
    sc = bd.add(Scope(n_in=1, labels=["y"], name="scope"))
    bd.connect(ref, err[0]); bd.connect(plant, err[1])
    bd.connect(err, kp); bd.connect(err, integ); bd.connect(integ, ki)
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
