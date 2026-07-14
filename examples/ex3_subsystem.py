"""예제 3 — 서브시스템: PI 제어기를 하나의 블록으로 묶는다.

Simulink 의 subsystem 과 같은 개념:
  · 내부 Diagram + Inport/Outport 가 경계
  · 실행 전에 flatten 으로 펼쳐진다 (Simulink 의 virtual subsystem 과 동일)
  · feedthrough 는 자동 분석 — 내부가 적분기로 막혀 있으면 피드백 루프에
    넣어도 대수 루프가 되지 않는다

뷰어(HTML)에서는 Shift+클릭으로 블록들을 다중 선택한 뒤
"서브시스템으로 묶기" 버튼으로 같은 일을 GUI 로 할 수 있다.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from loopsym import (
    Diagram, Step, Sum, Gain, Integrator, TransferFunction,
    Inport, Outport, Subsystem, Scope, run, render_html,
)

# --- PI 제어기 내부 다이어그램 ---
# 게인을 "$Kp"/"$Ki" 로 두면 마스크 파라미터가 된다 (Simulink mask 대응).
# 같은 서브시스템을 params 만 바꿔 여러 개 재사용할 수 있다.
pi_d = Diagram()
e   = pi_d.add(Inport(0, name="e"))
kp  = pi_d.add(Gain(k="$Kp", name="Kp"))
it  = pi_d.add(Integrator(name="err_int"))
ki  = pi_d.add(Gain(k="$Ki", name="Ki"))
add = pi_d.add(Sum("++", name="add"))
u   = pi_d.add(Outport(0, name="u"))
pi_d.connect(e, kp); pi_d.connect(e, it); pi_d.connect(it, ki)
pi_d.connect(kp, add[0]); pi_d.connect(ki, add[1]); pi_d.connect(add, u)

# --- 최상위: ref -> err -> [PI_ctrl(Kp=3, Ki=2)] -> plant -> scope ---
bd = Diagram()
ref   = bd.add(Step(t_on=1.0, name="ref"))
err   = bd.add(Sum("+-", name="err"))
ctrl  = bd.add(Subsystem(pi_d, params={"Kp": 3.0, "Ki": 2.0}, name="PI_ctrl"))
plant = bd.add(TransferFunction([1], [1, 2, 1], name="plant"))
scope = bd.add(Scope(n_in=2, labels=["ref", "y"], name="scope"))
bd.connect(ref, err[0]); bd.connect(plant, err[1])
bd.connect(err, ctrl); bd.connect(ctrl, plant)
bd.connect(ref, scope[0]); bd.connect(plant, scope[1])

print("PI_ctrl.feedthrough =", ctrl.feedthrough, "(Kp 직결 경로 → True)")
run(bd, t_end=10.0, dt=0.01)

plt.figure(figsize=(8, 4))
for i, lab in enumerate(scope.labels):
    plt.plot(scope.t, scope.data[i], label=lab)
plt.xlabel("time [s]"); plt.legend(); plt.grid(True)
plt.title("PI subsystem closed loop — loopsym")
out = os.path.join(os.path.dirname(__file__), "ex3_result.png")
plt.savefig(out, dpi=110, bbox_inches="tight")
print("plot :", out)
print("html :", render_html(bd, os.path.join(os.path.dirname(__file__), "ex3_diagram.html"),
                            title="ex3 — PI subsystem"))
print("y(10s) =", scope.data[1][-1])
