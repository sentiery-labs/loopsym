"""6주차 채점기 — 적분기·오일러·RK4. 최종전: 폐루프가 loopsym 과 일치해야 한다."""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", ".."))

import myblocks as mb                                   # noqa: E402
import mysim                                            # noqa: E402
from mydiagram import Diagram                           # noqa: E402
import loopsym as bs                                   # noqa: E402


def test_integrator_interface():
    it = mb.Integrator(x0=2.5)
    assert it.feedthrough is False and it.state_size == 1
    assert it.initial() == (2.5,)
    assert it.output(0.0, None, (7.0,)) == (7.0,)       # 출력 = 상태 (입력 무시!)
    assert it.derivative(0.0, (3.0,), (7.0,)) == (3.0,)  # 미분 = 입력


def _decay(method, dt):
    """dx/dt = -x, x(0)=1 → x(1) = e^-1."""
    bd = Diagram()
    zero = bd.add(mb.Constant(0.0))
    neg = bd.add(mb.Sum("+-"))
    it = bd.add(mb.Integrator(x0=1.0))
    sc = bd.add(mb.Scope())
    bd.connect(zero, neg[0]); bd.connect(it, neg[1])
    bd.connect(neg, it); bd.connect(it, sc)
    mysim.simulate(bd, 1.0, dt, method=method)
    return abs(sc.data[0][-1] - math.exp(-1))


def test_euler_error_scales_with_dt():
    """오일러 오차 ∝ dt — 1주차 리포트의 자동판."""
    e1, e2 = _decay("euler", 0.01), _decay("euler", 0.001)
    assert 1e-5 < e2 < 1e-3 and 5.0 < e1 / e2 < 20.0    # 대략 10배


def test_rk4_is_accurate():
    assert _decay("rk4", 0.001) < 1e-9


def test_scope_records_every_major_step():
    bd = Diagram()
    c = bd.add(mb.Constant(1.0)); sc = bd.add(mb.Scope())
    bd.connect(c, sc)
    mysim.simulate(bd, 1.0, 0.1)
    assert len(sc.t) == 11 and sc.t[0] == 0.0 and abs(sc.t[-1] - 1.0) < 1e-12


def _pi_loop(engine):
    """같은 PI 폐루프를 학생 엔진/loopsym 양쪽에 짓는다 (플랜트 = 적분기 2개)."""
    if engine == "mine":
        D, C, S, G, I, SC = Diagram, mb.Constant, mb.Sum, mb.Gain, mb.Integrator, mb.Scope
        step = mb.Step(t_on=1.0)
    else:
        D, C, S, G, I, SC = bs.Diagram, bs.Constant, bs.Sum, bs.Gain, bs.Integrator, bs.Scope
        step = bs.Step(t_on=1.0)
    bd = D()
    ref = bd.add(step)
    err = bd.add(S("+-")); kp = bd.add(G(3.0)); integ = bd.add(I()); ki = bd.add(G(2.0))
    pi = bd.add(S("++"))
    sp = bd.add(S("+--")); xd = bd.add(I()); x = bd.add(I()); damp = bd.add(G(2.0))
    sc = bd.add(SC(n_in=1))
    bd.connect(ref, err[0]); bd.connect(x, err[1])
    bd.connect(err, kp); bd.connect(err, integ); bd.connect(integ, ki)
    bd.connect(kp, pi[0]); bd.connect(ki, pi[1])
    bd.connect(pi, sp[0]); bd.connect(xd, damp); bd.connect(damp, sp[1]); bd.connect(x, sp[2])
    bd.connect(sp, xd); bd.connect(xd, x); bd.connect(x, sc)
    return bd, sc


def test_closed_loop_matches_loopsym():
    """★내 엔진의 폐루프 응답이 정식 loopsym 과 1e-9 이내 — 6주차 졸업 시험."""
    bd_m, sc_m = _pi_loop("mine")
    mysim.simulate(bd_m, 10.0, 0.01)
    bd_o, sc_o = _pi_loop("oracle")
    bs.run(bd_o, 10.0, 0.01)
    assert len(sc_m.data[0]) == len(sc_o.data[0])
    err = max(abs(a - b) for a, b in zip(sc_m.data[0], sc_o.data[0]))
    assert err < 1e-9, f"loopsym 과 최대차 {err}"
