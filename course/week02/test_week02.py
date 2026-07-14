"""2주차 채점기 — 블록 규약 + 출력을 loopsym 오라클과 대조."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", ".."))

import myblocks as mb                                   # noqa: E402
import loopsym as bs                                   # noqa: E402

US = [-3.0, -1.0, -0.2, 0.0, 0.7, 1.0, 2.5, 100.0]


def test_gain_matches_oracle():
    mine, oracle = mb.Gain(k=-1.7), bs.Gain(k=-1.7)
    for u in US:
        assert mine.output(0.0, (u,), ()) == (oracle.output(0.0, (u,), ())[0],)


def test_gain_interface():
    g = mb.Gain(2.0)
    assert g.n_in == 1 and g.n_out == 1
    assert isinstance(g.output(0.0, (3.0,), ()), tuple)


def test_saturation_matches_oracle():
    mine, oracle = mb.Saturation(lo=-0.5, hi=1.2), bs.Saturation(lo=-0.5, hi=1.2)
    for u in US:
        assert mine.output(0.0, (u,), ()) == (oracle.output(0.0, (u,), ())[0],), f"u={u}"


def test_saturation_stores_params():
    s = mb.Saturation(lo=-2.0, hi=3.0)
    assert s.lo == -2.0 and s.hi == 3.0


def test_offset():
    o = mb.Offset(c=1.5)
    assert o.n_in == 1
    for u in US:
        assert o.output(0.0, (u,), ()) == (u + 1.5,), f"u={u}"


def test_offset_default_and_name():
    assert mb.Offset().output(0.0, (2.0,), ()) == (2.0,)
    assert mb.Offset(name="bias").name == "bias"


def test_blocks_are_independent_instances():
    """파라미터가 클래스가 아니라 '인스턴스'에 산다는 것 — 2주차 핵심."""
    a, b = mb.Gain(2.0), mb.Gain(5.0)
    assert a.output(0, (1.0,), ()) == (2.0,) and b.output(0, (1.0,), ()) == (5.0,)
