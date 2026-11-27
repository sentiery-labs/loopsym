"""loopsym 파이썬 엔진 회귀 테스트 — WORKPLAN §6 기준값의 진실.

실행: loopsym/ 저장소 루트에서  python3 -m pytest tests/ -q
"""

import json
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loopsym import (            # noqa: E402
    AlgebraicLoopError, Constant, Demux, Diagram, DiscreteIntegrator, Gain,
    Inport, Integrator, Mux, Outport, Product, PyFunction, Scope, Step,
    Subsystem, Sum, TransferFunction, UnitDelay, load_json, run, save_json,
    export_json,
)


def make_pi_loop(ctrl_builder):
    """ref->err->[ctrl]->plant(1/(s²+2s+1))->scope 폐루프 골격."""
    bd = Diagram()
    ref = bd.add(Step(t_on=1.0, name="ref"))
    err = bd.add(Sum("+-", name="err"))
    ctrl_out = ctrl_builder(bd, err)
    plant = bd.add(TransferFunction([1], [1, 2, 1], name="plant"))
    sc = bd.add(Scope(n_in=1, name="sc"))
    bd.connect(ref, err[0])
    bd.connect(plant, err[1])
    bd.connect(ctrl_out, plant)
    bd.connect(plant, sc)
    return bd, sc


def continuous_pi(bd, err):
    kp = bd.add(Gain(3.0)); it = bd.add(Integrator()); ki = bd.add(Gain(2.0))
    add = bd.add(Sum("++"))
    bd.connect(err, kp); bd.connect(err, it); bd.connect(it, ki)
    bd.connect(kp, add[0]); bd.connect(ki, add[1])
    return add


# ---------------------------------------------------------------- 기준값
def test_rk4_accuracy():
    """dx/dt = -x, x(0)=1 -> x(1)=e^-1 (오차 < 1e-9)."""
    bd = Diagram()
    g = bd.add(Gain(-1.0)); it = bd.add(Integrator(x0=1.0)); sc = bd.add(Scope())
    bd.connect(it, g); bd.connect(g, it); bd.connect(it, sc)
    run(bd, 1.0, 0.01)
    assert abs(sc.data[0][-1] - math.exp(-1)) < 1e-9


def test_pi_loop_baseline():
    bd, sc = make_pi_loop(continuous_pi)
    run(bd, 10.0, 0.01)
    assert abs(sc.data[0][-1] - 1.000189) < 1e-6


def test_pendulum_pyfunction_baseline():
    bd = Diagram()
    ref = bd.add(Step(t_on=1.0, height=0.8))
    ctrl = bd.add(PyFunction("6.0*(u0-u1) - 2.0*u2", n_in=3))
    dyn = bd.add(PyFunction("-(9.81/1.0)*sin(u0) - 0.3*u1 + u2", n_in=3))
    om = bd.add(Integrator()); th = bd.add(Integrator()); sc = bd.add(Scope())
    bd.connect(ref, ctrl[0]); bd.connect(th, ctrl[1]); bd.connect(om, ctrl[2])
    bd.connect(th, dyn[0]); bd.connect(om, dyn[1]); bd.connect(ctrl, dyn[2])
    bd.connect(dyn, om); bd.connect(om, th); bd.connect(th, sc)
    run(bd, 8.0, 0.005)
    assert abs(sc.data[0][-1] - 0.306499) < 1e-6


def test_tf_dc_gain():
    bd = Diagram()
    st = bd.add(Step(t_on=0.0)); tf = bd.add(TransferFunction([2, 3], [1, 2, 1]))
    sc = bd.add(Scope())
    bd.connect(st, tf); bd.connect(tf, sc)
    run(bd, 30.0, 0.01)
    assert abs(sc.data[0][-1] - 3.0) < 1e-6


def test_algebraic_loop_detected():
    bd = Diagram()
    g1 = bd.add(Gain(1.0)); g2 = bd.add(Gain(1.0))
    bd.connect(g1, g2); bd.connect(g2, g1)
    with pytest.raises(AlgebraicLoopError):
        bd.compile()


def test_unconnected_port_error():
    bd = Diagram()
    bd.add(Gain(1.0))
    with pytest.raises(ValueError, match="연결되지 않음"):
        bd.compile()


def test_product():
    bd = Diagram()
    a = bd.add(Constant(6.0)); b = bd.add(Constant(2.0)); c = bd.add(Constant(3.0))
    pr = bd.add(Product("**/")); sc = bd.add(Scope())
    bd.connect(a, pr[0]); bd.connect(b, pr[1]); bd.connect(c, pr[2]); bd.connect(pr, sc)
    run(bd, 0.1, 0.1)
    assert sc.data[0][-1] == pytest.approx(4.0)


# ---------------------------------------------------------------- 서브시스템
def pi_subsystem(mask=False):
    d = Diagram()
    e = d.add(Inport(0)); kp = d.add(Gain(k="$Kp" if mask else 3.0, name="Kp"))
    it = d.add(Integrator()); ki = d.add(Gain(k="$Ki" if mask else 2.0, name="Ki"))
    add = d.add(Sum("++")); o = d.add(Outport(0))
    d.connect(e, kp); d.connect(e, it); d.connect(it, ki)
    d.connect(kp, add[0]); d.connect(ki, add[1]); d.connect(add, o)
    return d


def sub_builder(mask):
    def build(bd, err):
        kw = {"params": {"Kp": 3.0, "Ki": 2.0}} if mask else {}
        s = bd.add(Subsystem(pi_subsystem(mask), **kw, name="PI"))
        bd.connect(err, s)
        return s
    return build


def test_subsystem_equals_flat():
    for mask in (False, True):
        bd, sc = make_pi_loop(sub_builder(mask))
        run(bd, 10.0, 0.01)
        assert abs(sc.data[0][-1] - 1.000189) < 1e-6, f"mask={mask}"


def test_subsystem_feedthrough_analysis():
    d = Diagram()
    i = d.add(Inport(0)); tf = d.add(TransferFunction([1], [1, 1])); o = d.add(Outport(0))
    d.connect(i, tf); d.connect(tf, o)
    assert Subsystem(d).feedthrough is False       # 적분기로 막힘
    assert Subsystem(pi_subsystem()).feedthrough is True   # Kp 직결 경로


def test_mask_unresolved_stays_string():
    d = pi_subsystem(mask=True)
    sub = Subsystem(d, params={"Kp": 3.0})   # Ki 는 안 채움
    kp = [b for b in d.blocks if b.name == "Kp"][0]
    ki = [b for b in d.blocks if b.name == "Ki"][0]
    assert kp.k == 3.0 and ki.k == "$Ki"


# ---------------------------------------------------------------- 이산시간
def test_discrete_integrator_forward_euler():
    bd = Diagram()
    c = bd.add(Constant(1.0)); di = bd.add(DiscreteIntegrator(st=0.1)); sc = bd.add(Scope())
    bd.connect(c, di); bd.connect(di, sc)
    run(bd, 1.0, 0.01)
    assert sc.data[0][-1] == pytest.approx(1.0)    # 0.1 × 10 샘플


def test_unit_delay():
    bd = Diagram()
    st = bd.add(Step(t_on=0.2)); ud = bd.add(UnitDelay(st=0.1)); sc = bd.add(Scope(n_in=2))
    bd.connect(st, ud); bd.connect(st, sc[0]); bd.connect(ud, sc[1])
    run(bd, 0.5, 0.05)
    at = {round(t, 3): (u, y) for t, u, y in zip(sc.t, sc.data[0], sc.data[1])}
    assert at[0.2] == (1.0, 0.0) and at[0.3] == (1.0, 1.0)   # 정확히 1샘플 지연


def test_discrete_pi_baseline():
    def discrete_pi(bd, err):
        kp = bd.add(Gain(3.0)); di = bd.add(DiscreteIntegrator(st=0.01)); ki = bd.add(Gain(2.0))
        add = bd.add(Sum("++"))
        bd.connect(err, kp); bd.connect(err, di); bd.connect(di, ki)
        bd.connect(kp, add[0]); bd.connect(ki, add[1])
        return add
    bd, sc = make_pi_loop(discrete_pi)
    run(bd, 10.0, 0.01)
    assert abs(sc.data[0][-1] - 1.000087) < 1e-6


def test_sample_time_must_divide_dt():
    bd = Diagram()
    c = bd.add(Constant(1.0)); di = bd.add(DiscreteIntegrator(st=0.015)); sc = bd.add(Scope())
    bd.connect(c, di); bd.connect(di, sc)
    with pytest.raises(ValueError, match="정수배"):
        run(bd, 1.0, 0.01)


# ---------------------------------------------------------------- Mux / 저장·불러오기
def test_mux_demux_roundtrip():
    bd = Diagram()
    a = bd.add(Constant(1.5)); b = bd.add(Constant(-2.0))
    mx = bd.add(Mux(2)); dm = bd.add(Demux(2)); sc = bd.add(Scope(n_in=2))
    bd.connect(a, mx[0]); bd.connect(b, mx[1]); bd.connect(mx, dm)
    bd.connect(dm[0], sc[0]); bd.connect(dm[1], sc[1])
    run(bd, 0.1, 0.1)
    assert (sc.data[0][-1], sc.data[1][-1]) == (1.5, -2.0)


def test_vector_into_scope_rejected():
    bd = Diagram()
    a = bd.add(Constant(1.0)); mx = bd.add(Mux(1)); sc = bd.add(Scope())
    bd.connect(a, mx); bd.connect(mx, sc)
    with pytest.raises(ValueError, match="Demux"):
        run(bd, 0.1, 0.1)


def test_save_load_roundtrip(tmp_path):
    bd, sc = make_pi_loop(sub_builder(True))
    p = str(tmp_path / "m.json")
    save_json(bd, p)
    bd2 = load_json(p)
    sc2 = [b for b in bd2.blocks if isinstance(b, Scope)][0]
    run(bd2, 10.0, 0.01)
    assert abs(sc2.data[0][-1] - 1.000189) < 1e-6
    # 좌표 보존: 다시 내보내도 같은 위치
    j1, j2 = export_json(bd2), json.loads(open(p, encoding="utf-8").read())
    pos1 = {b["name"]: (b["x"], b["y"]) for b in j1["blocks"]}
    pos2 = {b["name"]: (b["x"], b["y"]) for b in j2["blocks"]}
    assert pos1 == pos2


# ---------------------------------------------------------------- 함수형 PyFunction
def test_pyfunction_def_form_inference():
    """def 형: 시그니처에서 포트 수/이름, return 에서 출력 수 자동 추론."""
    p = PyFunction("def ctrl(t, ref, y):\n    e = ref - y\n    return 3*e, 2*e")
    assert (p.n_in, p.n_out) == (2, 2)
    assert p.in_names == ["ref", "y"]
    assert p.output(0.0, (5.0, 2.0), ()) == (9.0, 6.0)


def test_pyfunction_def_form_helpers_and_no_t():
    """여러 def = 마지막이 블록 함수(위는 헬퍼), t 는 선택."""
    p = PyFunction("def sq(x):\n    return x*x\n"
                   "def dist(a, b):\n    return sqrt(sq(a) + sq(b))")
    assert (p.n_in, p.n_out) == (2, 1)
    assert p.output(0, (3.0, 4.0), ()) == (5.0,)


def test_pyfunction_def_form_requires_return():
    with pytest.raises(ValueError, match="return"):
        PyFunction("def f(a):\n    x = a")


def test_pyfunction_def_form_closed_loop_and_roundtrip():
    """def 형 제어기(P 항)로 PI 폐루프 — 기준값 재현 + JSON 라운드트립.

    함수형은 무상태다 — 적분은 Integrator 블록 몫 (Simulink MFcn 과 동일 원칙)."""
    bd = Diagram()
    ref = bd.add(Step(t_on=1.0)); err = bd.add(Sum("+-"))
    kp = bd.add(PyFunction("def p_ctrl(e):\n    return 3.0*e"))
    it = bd.add(Integrator()); ki = bd.add(Gain(2.0)); add = bd.add(Sum("++"))
    plant = bd.add(TransferFunction([1], [1, 2, 1])); sc = bd.add(Scope())
    bd.connect(ref, err[0]); bd.connect(plant, err[1])
    bd.connect(err, kp); bd.connect(err, it); bd.connect(it, ki)
    bd.connect(kp, add[0]); bd.connect(ki, add[1]); bd.connect(add, plant)
    bd.connect(plant, sc)
    run(bd, 10.0, 0.01)
    assert abs(sc.data[0][-1] - 1.000189) < 1e-6
    # JSON 라운드트립 (def 형 expr 문자열 보존)
    j = export_json(bd)
    bd2 = load_json(j)
    sc2 = [b for b in bd2.blocks if isinstance(b, Scope)][0]
    run(bd2, 10.0, 0.01)
    assert sc2.data[0][-1] == sc.data[0][-1]


# ---------------------------------------------------------------- 실행 끝 / 링크 찾기 고리
from loopsym.core import Block   # noqa: E402
from loopsym.sim import Simulator   # noqa: E402


class Counter(Block):
    """시험용: finish 호출 수, resolve_links 로 받은 블록 목록을 기록하는 통과 블록."""
    n_in = 1
    n_out = 1

    def __init__(self, fail_finish=False, name=None):
        super().__init__(name)
        self.finished = 0
        self.links_calls = []
        self.fail_finish = fail_finish

    def output(self, t, u, x):
        return (u[0],)

    def resolve_links(self, blocks):
        self.links_calls.append(list(blocks))

    def finish(self):
        self.finished += 1
        if self.fail_finish:
            raise ValueError("finish 실패")


class Boom(Block):
    """시험용: t ≥ 0.5 에서 RuntimeError."""
    n_in = 0
    n_out = 1

    def output(self, t, u, x):
        if t >= 0.5:
            raise RuntimeError("붐")
        return (1.0,)


def _counter_diagram(src=None, fail_finish=False):
    bd = Diagram()
    s = bd.add(src or Constant(1.0))
    c = bd.add(Counter(fail_finish=fail_finish))
    sc = bd.add(Scope())
    bd.connect(s, c)
    bd.connect(c, sc)
    return bd, c


def test_finish_called_once_after_run():
    bd, c = _counter_diagram()
    run(bd, 1.0, 0.01)
    assert c.finished == 1


def test_finish_called_when_iteration_stops_early():
    import threading
    from loopsym.realtime import run_realtime
    bd, c = _counter_diagram()
    ev = threading.Event()
    ev.set()
    stats = run_realtime(bd, 10.0, 0.01, stop_event=ev, pin=False)
    assert stats["stopped"] is True
    assert c.finished == 1


def test_finish_called_when_block_raises():
    bd, c = _counter_diagram(src=Boom())
    with pytest.raises(RuntimeError, match="붐"):
        run(bd, 1.0, 0.01)
    assert c.finished == 1


def test_finish_error_does_not_mask_run_error():
    bd, c = _counter_diagram(src=Boom(), fail_finish=True)
    with pytest.warns(UserWarning, match="finish 실패"):
        with pytest.raises(RuntimeError, match="붐"):
            run(bd, 1.0, 0.01)
    assert c.finished == 1


def test_finish_error_raised_after_normal_run():
    bd, c = _counter_diagram(fail_finish=True)
    with pytest.raises(ValueError, match="finish 실패"):
        run(bd, 0.1, 0.01)


def test_resolve_links_gets_flattened_blocks():
    inner = Diagram()
    i = inner.add(Inport(0))
    c = inner.add(Counter(name="inner_counter"))
    o = inner.add(Outport(0))
    inner.connect(i, c)
    inner.connect(c, o)
    bd = Diagram()
    k = bd.add(Constant(2.0))
    sub = bd.add(Subsystem(inner, name="S"))
    sc = bd.add(Scope())
    bd.connect(k, sub)
    bd.connect(sub, sc)
    Simulator(bd)
    assert len(c.links_calls) == 1
    names = {b.name for b in c.links_calls[0]}
    assert "inner_counter" in names and "S" not in names
