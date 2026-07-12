"""예제 2 — PyFunction 블록 (MATLAB Function 블록의 파이썬판).

비선형 진자를 PD 제어로 목표각까지 세운다.
  진자 동역학:  θ'' = -(g/L)·sin(θ) - b·θ' + u
  제어기:       u = Kp(ref-θ) - Kd·θ'

두 군데 모두 PyFunction 하나로 끝난다 — Simulink 에서 MATLAB Function
블록에 수식을 쓰는 것과 같은 감각.

[교육 포인트] θ 는 0.8 이 아니라 ~0.31 rad 에 머문다. 중력 토크
g·sin(θ) 를 이기려면 정상상태에서도 u ≠ 0 이어야 하는데, PD 는 오차가
있어야만 토크를 내기 때문. → "왜 적분항(I)이 필요한가"의 실물 예제.
ctrl 식에 적분 경로를 추가해 오차를 없애 보는 것이 과제.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from blocksim import Diagram, Step, PyFunction, Integrator, Scope, run, render_html

bd = Diagram()

ref   = bd.add(Step(t_on=1.0, height=0.8, name="ref"))                 # 목표각 0.8 rad
ctrl  = bd.add(PyFunction("6.0*(u0-u1) - 2.0*u2", n_in=3, name="PD_ctrl"))
dyn   = bd.add(PyFunction("-(9.81/1.0)*sin(u0) - 0.3*u1 + u2", n_in=3, name="pendulum"))
omega = bd.add(Integrator(name="omega"))    # θ'' -> θ'
theta = bd.add(Integrator(name="theta"))    # θ'  -> θ
scope = bd.add(Scope(n_in=2, labels=["ref", "theta"], name="scope"))

bd.connect(ref,   ctrl[0])   # u0 = 목표각
bd.connect(theta, ctrl[1])   # u1 = 현재각 (피드백)
bd.connect(omega, ctrl[2])   # u2 = 각속도 (피드백)

bd.connect(theta, dyn[0])    # u0 = θ
bd.connect(omega, dyn[1])    # u1 = θ'
bd.connect(ctrl,  dyn[2])    # u2 = 제어 토크

bd.connect(dyn,   omega)
bd.connect(omega, theta)
bd.connect(ref,   scope[0])
bd.connect(theta, scope[1])

run(bd, t_end=8.0, dt=0.005)

plt.figure(figsize=(8, 4))
for i, lab in enumerate(scope.labels):
    plt.plot(scope.t, scope.data[i], label=lab)
plt.xlabel("time [s]"); plt.ylabel("angle [rad]"); plt.legend(); plt.grid(True)
plt.title("Nonlinear pendulum + PD (PyFunction blocks)")
out = os.path.join(os.path.dirname(__file__), "ex2_result.png")
plt.savefig(out, dpi=110, bbox_inches="tight")
print("plot :", out)
print("html :", render_html(bd, os.path.join(os.path.dirname(__file__), "ex2_diagram.html"),
                            title="ex2 — pendulum + PyFunction"))
print("theta(8s) =", scope.data[1][-1])
