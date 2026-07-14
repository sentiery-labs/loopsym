"""4주차 채점기 — 연결 검증 + 위상 정렬의 '성질' 검사.

순서 자체는 여러 답이 가능하므로, "모든 블록이 자기에게 입력을 주는
블록들보다 뒤에 온다" 는 성질로 채점한다.
"""

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", ".."))

from myblocks import Constant, Gain, Sum, Scope          # noqa: E402
from mydiagram import Diagram                            # noqa: E402


def chain():
    bd = Diagram()
    c = bd.add(Constant(1.0, name="c"))
    g1 = bd.add(Gain(2.0, name="g1"))
    g2 = bd.add(Gain(3.0, name="g2"))
    sc = bd.add(Scope(name="sc"))
    return bd, c, g1, g2, sc


def test_connect_registers_wire():
    bd, c, g1, g2, sc = chain()
    bd.connect(c, g1)
    assert bd.wires[(g1, 0)] == (c, 0)


def test_connect_rejects_bad_out_port():
    bd, c, g1, *_ = chain()
    with pytest.raises(ValueError):
        bd.connect(c[1], g1)          # Constant 출력은 0번뿐


def test_connect_rejects_bad_in_port():
    bd, c, g1, *_ = chain()
    with pytest.raises(ValueError):
        bd.connect(c, g1[3])          # Gain 입력은 0번뿐


def test_connect_rejects_duplicate_driver():
    bd, c, g1, g2, _ = chain()
    bd.connect(c, g1)
    with pytest.raises(ValueError):
        bd.connect(g2, g1)            # g1 입력은 이미 c 가 잡았다


def test_compile_rejects_unconnected_input():
    bd, c, g1, *_ = chain()
    bd.connect(c, g1)                 # g2, sc 는 미연결
    with pytest.raises(ValueError):
        bd.compile()


def _assert_topological(order, bd):
    pos = {b: i for i, b in enumerate(order)}
    assert sorted(pos.values()) == list(range(len(bd.blocks))), "순서에 전 블록이 한 번씩"
    for (dst, _i), (src, _j) in bd.wires.items():
        assert pos[src] < pos[dst], f"{src.name} 가 {dst.name} 보다 먼저 와야 함"


def test_compile_chain_order():
    bd, c, g1, g2, sc = chain()
    bd.connect(c, g1); bd.connect(g1, g2); bd.connect(g2, sc)
    _assert_topological(bd.compile(), bd)


def test_compile_diamond_order():
    """한 소스 → 두 경로 → Sum (수업의 다이아몬드 예제)."""
    bd = Diagram()
    c = bd.add(Constant(1.0, name="c"))
    a = bd.add(Gain(2.0, name="a"))
    b = bd.add(Gain(3.0, name="b"))
    s = bd.add(Sum("++", name="s"))
    sc = bd.add(Scope(name="sc"))
    bd.connect(c, a); bd.connect(c, b)
    bd.connect(a, s[0]); bd.connect(b, s[1]); bd.connect(s, sc)
    _assert_topological(bd.compile(), bd)


def test_compile_detects_cycle():
    """이번 주 가정(전부 feedthrough)에서 고리는 에러 (종류는 아직 안 따진다)."""
    bd = Diagram()
    g1 = bd.add(Gain(2.0, name="g1"))
    g2 = bd.add(Gain(0.4, name="g2"))
    bd.connect(g1, g2); bd.connect(g2, g1)
    with pytest.raises(Exception):
        bd.compile()
