"""Rangefinder — 아래 방향 거리계 (ideal / noisy / world)."""

import math

import pytest

from loopsym import Constant, Diagram, Inport, Outport, Scope, Simulator, Subsystem, run
from loopsym.sensors import Rangefinder
from loopsym.world import WorldLink
from tests.fake_world import FakeWorld

DT = 0.01


def _state(q=(1.0, 0.0, 0.0, 0.0), p_down=-10.0):
    return tuple(q) + (0.0, 0.0, 0.0) + (0.0, 0.0, p_down) + (0.0, 0.0, 0.0)


def _roll(deg):
    a = math.radians(deg) / 2.0
    return (math.cos(a), math.sin(a), 0.0, 0.0)


def test_ideal_level_hover():
    assert Rangefinder().output(0.0, _state(), (0.0,)) == (10.0, 1.0)


def test_ideal_roll_60deg():
    r, v = Rangefinder().output(0.0, _state(q=_roll(60)), (0.0,))
    assert r == pytest.approx(20.0, abs=1e-9) and v == 1.0


def test_ideal_inverted_invalid():
    assert Rangefinder().output(0.0, _state(q=_roll(180)), (0.0,)) == (100.0, 0.0)


def test_ideal_beyond_max_invalid():
    assert Rangefinder().output(0.0, _state(p_down=-150.0), (0.0,)) == (100.0, 0.0)


def test_ideal_on_ground_zero():
    assert Rangefinder().output(0.0, _state(p_down=0.0), (0.0,)) == (0.0, 1.0)


def _const_diagram(sensor, state=None):
    """상수 상태 13개 → sensor → Scope(2)."""
    bd = Diagram()
    rf = bd.add(sensor)
    consts = [bd.add(Constant(float(v))) for v in (state or _state())]
    for i, c in enumerate(consts):
        bd.connect(c, rf[i])
    sc = bd.add(Scope(2, labels=["range", "valid"]))
    bd.connect(rf[0], sc[0])
    bd.connect(rf[1], sc[1])
    return bd, consts, sc


def test_noisy_seeded_reproducible():
    runs = []
    for _ in range(2):
        bd, _, sc = _const_diagram(Rangefinder(fidelity="noisy", seed=7, noise_sd=0.05))
        run(bd, 0.4, DT)
        runs.append(list(sc.data[0]))
    assert runs[0] == runs[1]
    assert any(abs(r - 10.0) > 1e-6 for r in runs[0])
    assert all(r >= 0.0 for r in runs[0])


def _world_diagram(port, rf, link_kw=None):
    """상수 상태 → WorldLink(+모터 0.5) 와 Rangefinder 가 같은 상태를 받는다."""
    bd, consts, sc = _const_diagram(rf)
    link = bd.add(WorldLink(port=port, st=0.04, name="link", **(link_kw or {})))
    for i, c in enumerate(consts):
        bd.connect(c, link[i])
    for i in range(4):
        bd.connect(bd.add(Constant(0.5)), link[13 + i])
    return bd, link, sc


def test_world_reads_frame_with_delay():
    with FakeWorld(respond=lambda s: ({"range_m": 42.0, "range_valid": True}, b"")) as w:
        bd, _, sc = _world_diagram(w.port, Rangefinder(fidelity="world"))
        run(bd, 0.2, DT)
    for t, r, v in zip(sc.t, sc.data[0], sc.data[1]):
        if t < 0.04 - 1e-9:
            assert (r, v) == (100.0, 0.0), t
        else:
            assert (r, v) == (42.0, 1.0), t


def test_world_invalid_frame():
    with FakeWorld(respond=lambda s: ({"range_m": None, "range_valid": False}, b"")) as w:
        bd, _, sc = _world_diagram(w.port, Rangefinder(fidelity="world", max_range=80.0))
        run(bd, 0.2, DT)
    assert set(zip(sc.data[0], sc.data[1])) == {(80.0, 0.0)}


def test_hello_carries_max_range():
    with FakeWorld() as w:
        bd, _, _ = _world_diagram(w.port, Rangefinder(fidelity="world"))
        run(bd, 0.08, DT)
    assert w.received[0]["rangefinder"] == {"max_m": 100.0}


def test_ports_same_for_all_fidelity():
    for f in ("ideal", "noisy", "world"):
        rf = Rangefinder(fidelity=f)
        assert (rf.n_in, rf.n_out) == (13, 2), f
    with pytest.raises(NotImplementedError):
        Rangefinder(fidelity="hardware")


def test_link_resolution_inside_subsystem():
    inner = Diagram()
    link = inner.add(WorldLink(name="inner_link"))
    for i in range(link.n_in):
        inner.connect(inner.add(Constant(0.0)), link[i])
    out = inner.add(Outport(0))
    inner.connect(link[0], out)
    bd, _, _ = _const_diagram(Rangefinder(fidelity="world", link="inner_link"))
    rf = bd.blocks[0]
    sub = bd.add(Subsystem(inner, name="World"))
    sc = bd.add(Scope())
    bd.connect(sub, sc)
    Simulator(bd)
    assert link.rangefinder is rf


def test_ambiguous_link_raises():
    bd, consts, _ = _const_diagram(Rangefinder(fidelity="world"))
    for name in ("linkA", "linkB"):
        link = bd.add(WorldLink(name=name))
        for i, c in enumerate(consts):
            bd.connect(c, link[i])
        for i in range(4):
            bd.connect(bd.add(Constant(0.0)), link[13 + i])
    with pytest.raises(ValueError) as ei:
        Simulator(bd)
    assert "linkA" in str(ei.value) and "linkB" in str(ei.value)


def test_second_world_rangefinder_on_same_link_raises():
    bd, consts, _ = _const_diagram(Rangefinder(fidelity="world"))
    rf2 = bd.add(Rangefinder(fidelity="world", name="rf2"))
    link = bd.add(WorldLink(name="link"))
    for i, c in enumerate(consts):
        bd.connect(c, rf2[i])
        bd.connect(c, link[i])
    for i in range(4):
        bd.connect(bd.add(Constant(0.0)), link[13 + i])
    sc = bd.add(Scope(2))
    bd.connect(rf2[0], sc[0])
    bd.connect(rf2[1], sc[1])
    with pytest.raises(ValueError, match="거리계"):
        Simulator(bd)
