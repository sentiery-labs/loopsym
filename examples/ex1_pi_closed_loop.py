"""예제 1 — PI 제어 폐루프.

          +-----+   e   +----------- PI ----------+  u  +-----------+
step ---->| Sum |------>| Kp*e  +  Ki*∫e dt       |---->| 1/(s²+2s+1)|--+--> scope
      +-->|  -  |       +-------------------------+     +-----------+  |
      |                                                                |
      +----------------------------------------------------------------
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from blocksim import (
    Diagram, Step, Sum, Gain, Integrator, TransferFunction, Scope, run, render_html,
)

bd = Diagram()

ref   = bd.add(Step(t_on=1.0, height=1.0, name="ref"))
err   = bd.add(Sum("+-", name="err"))
kp    = bd.add(Gain(k=3.0, name="Kp"))
integ = bd.add(Integrator(name="err_int"))
ki    = bd.add(Gain(k=2.0, name="Ki"))
pi    = bd.add(Sum("++", name="PI"))
plant = bd.add(TransferFunction([1], [1, 2, 1], name="plant"))
scope = bd.add(Scope(n_in=2, labels=["ref", "y"], name="scope"))

bd.connect(ref, err[0])
bd.connect(plant, err[1])        # 피드백 — Integrator/TF 가 루프를 끊어준다
bd.connect(err, kp)
bd.connect(err, integ)
bd.connect(integ, ki)
bd.connect(kp, pi[0])
bd.connect(ki, pi[1])
bd.connect(pi, plant)
bd.connect(ref, scope[0])
bd.connect(plant, scope[1])

run(bd, t_end=10.0, dt=0.01)

plt.figure(figsize=(8, 4))
for i, lab in enumerate(scope.labels):
    plt.plot(scope.t, scope.data[i], label=lab)
plt.xlabel("time [s]"); plt.ylabel("value"); plt.legend(); plt.grid(True)
plt.title("PI closed loop — blocksim")
out = os.path.join(os.path.dirname(__file__), "ex1_result.png")
plt.savefig(out, dpi=110, bbox_inches="tight")
print("plot :", out)
print("html :", render_html(bd, os.path.join(os.path.dirname(__file__), "ex1_diagram.html"),
                            title="ex1 — PI closed loop"))
print("y(10s) =", scope.data[1][-1])
