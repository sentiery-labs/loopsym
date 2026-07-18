"""번들 예제 JSON 생성 — CLI 데모의 정본 (loopsym/examples/*.json).

    python tools/gen_bundled_examples.py

wheel 에 패키지 데이터로 실리는 3종을 만든다 (UX 리뷰 차단 항목 4):
  pi          — PI 폐루프 (마스크 PI 서브시스템, ex1/ex3 = 회귀 기준 y(10s)=1.000189)
  pendulum    — 비선형 진자 + PD (ex2, θ(8s)=0.306499)
  discrete_pi — 이산 PI Ts=0.01 (ex4, y(10s)=1.000087)

뷰어 JS 의 demoModel() 폴백(원본 viewer.html 직접 열기 전용)은 pi 와 같은
구조를 유지한다 — 정본은 이 파일이다.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from loopsym import (                                     # noqa: E402
    Diagram, DiscreteIntegrator, Gain, Inport, Integrator, Outport, PyFunction,
    Scope, Step, Subsystem, Sum, TransferFunction,
)
from loopsym.viz import export_json                       # noqa: E402


def pi_model():
    """마스크 PI 서브시스템 폐루프 — 뷰어 demoModel() 과 동일 구조."""
    d = Diagram()
    e = d.add(Inport(0, name="e"))
    kp = d.add(Gain(k="$Kp", name="Kp"))
    it = d.add(Integrator(name="err_int"))
    ki = d.add(Gain(k="$Ki", name="Ki"))
    add = d.add(Sum("++", name="add"))
    u = d.add(Outport(0, name="u"))
    d.connect(e, kp); d.connect(e, it); d.connect(it, ki)
    d.connect(kp, add[0]); d.connect(ki, add[1]); d.connect(add, u)

    bd = Diagram()
    ref = bd.add(Step(t_on=1.0, name="ref"))
    err = bd.add(Sum("+-", name="err"))
    ctrl = bd.add(Subsystem(d, params={"Kp": 3.0, "Ki": 2.0}, name="PI_ctrl"))
    plant = bd.add(TransferFunction([1], [1, 2, 1], name="plant"))
    sc = bd.add(Scope(n_in=2, labels=["ref", "y"], name="scope"))
    bd.connect(ref, err[0]); bd.connect(plant, err[1])
    bd.connect(err, ctrl); bd.connect(ctrl, plant)
    bd.connect(ref, sc[0]); bd.connect(plant, sc[1])
    return bd


def pendulum_model():
    """비선형 진자 + PD (PyFunction) — 왜 적분항이 필요한가 (ex2)."""
    bd = Diagram()
    ref = bd.add(Step(t_on=1.0, height=0.8, name="theta_ref"))
    ctrl = bd.add(PyFunction("6.0*(u0-u1) - 2.0*u2", n_in=3, name="pd_ctrl"))
    dyn = bd.add(PyFunction("-(9.81/1.0)*sin(u0) - 0.3*u1 + u2", n_in=3, name="pendulum"))
    om = bd.add(Integrator(name="omega"))
    th = bd.add(Integrator(name="theta"))
    sc = bd.add(Scope(n_in=2, labels=["ref", "theta"], name="scope"))
    bd.connect(ref, ctrl[0]); bd.connect(th, ctrl[1]); bd.connect(om, ctrl[2])
    bd.connect(th, dyn[0]); bd.connect(om, dyn[1]); bd.connect(ctrl, dyn[2])
    bd.connect(dyn, om); bd.connect(om, th)
    bd.connect(ref, sc[0]); bd.connect(th, sc[1])
    return bd


def discrete_pi_model():
    """이산 PI (Ts=0.01) — 샘플링, PX4 로 가는 다리 (ex4)."""
    bd = Diagram()
    ref = bd.add(Step(t_on=1.0, name="ref"))
    err = bd.add(Sum("+-", name="err"))
    kp = bd.add(Gain(3.0, name="Kp"))
    di = bd.add(DiscreteIntegrator(st=0.01, name="err_int"))
    ki = bd.add(Gain(2.0, name="Ki"))
    add = bd.add(Sum("++", name="pi_sum"))
    plant = bd.add(TransferFunction([1], [1, 2, 1], name="plant"))
    sc = bd.add(Scope(n_in=2, labels=["ref", "y"], name="scope"))
    bd.connect(ref, err[0]); bd.connect(plant, err[1])
    bd.connect(err, kp); bd.connect(err, di); bd.connect(di, ki)
    bd.connect(kp, add[0]); bd.connect(ki, add[1]); bd.connect(add, plant)
    bd.connect(ref, sc[0]); bd.connect(plant, sc[1])
    return bd


MODELS = {"pi": pi_model, "pendulum": pendulum_model, "discrete_pi": discrete_pi_model}


def main():
    out = os.path.join(ROOT, "loopsym", "examples")
    os.makedirs(out, exist_ok=True)
    for name, build in MODELS.items():
        p = os.path.join(out, f"{name}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(export_json(build()), f, ensure_ascii=False, indent=1)
        print("생성:", os.path.relpath(p, ROOT))


if __name__ == "__main__":
    main()
