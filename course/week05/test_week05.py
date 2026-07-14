"""5주차 채점기 — 대수 루프 판별 (수업 과제: 모델 5개 판별을 자동화한 것)."""

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", ".."))

from myblocks import Constant, Gain, Sum, Scope, StateStub   # noqa: E402
from mydiagram import AlgebraicLoopError, Diagram            # noqa: E402


def test_pure_gain_loop_is_algebraic():
    """[모델 1] Gain 끼리 고리 = 대수 루프. 메시지에 블록 이름이 있어야 한다."""
    bd = Diagram()
    g1 = bd.add(Gain(2.0, name="g1"))
    g2 = bd.add(Gain(0.4, name="g2"))
    bd.connect(g1, g2); bd.connect(g2, g1)
    with pytest.raises(AlgebraicLoopError) as e:
        bd.compile()
    assert "g1" in str(e.value) and "g2" in str(e.value), "에러 메시지에 고리 블록 이름"


def test_loop_broken_by_state_block():
    """[모델 2] 고리에 상태 블록이 하나라도 있으면 OK — 피드백의 원리."""
    bd = Diagram()
    c = bd.add(Constant(1.0, name="ref"))
    e = bd.add(Sum("+-", name="err"))
    g = bd.add(Gain(3.0, name="ctrl"))
    p = bd.add(StateStub(name="plant"))
    bd.connect(c, e[0]); bd.connect(p, e[1])
    bd.connect(e, g); bd.connect(g, p)
    order = bd.compile()
    assert len(order) == 4


def test_state_block_has_no_order_constraint():
    """상태 블록은 소비자보다 늦게 와도 된다 — 하지만 feedthrough 소비자는
    자기 소스(상태 블록 포함)보다 뒤여야 한다."""
    bd = Diagram()
    p = bd.add(StateStub(name="plant"))
    g = bd.add(Gain(1.0, name="g"))
    sc = bd.add(Scope(name="sc"))
    bd.connect(p, g); bd.connect(g, sc)
    bd.connect(g, p)                            # g -> plant 피드백 (상태 블록이라 OK)
    order = bd.compile()
    pos = {b: i for i, b in enumerate(order)}
    assert pos[p] < pos[g] < pos[sc]


def test_two_loops_one_algebraic():
    """[모델 3] 상태 고리 + 순수 게인 고리가 공존하면 → 여전히 대수 루프."""
    bd = Diagram()
    p = bd.add(StateStub(name="plant"))
    a = bd.add(Sum("++", name="a"))
    b = bd.add(Gain(1.0, name="b"))
    bd.connect(p, a[0])
    bd.connect(a, b); bd.connect(b, a[1])       # a<->b 순수 고리
    bd.connect(b, p)
    with pytest.raises(AlgebraicLoopError):
        bd.compile()


def test_long_algebraic_chain_loop():
    """[모델 4] 3개 이상 거치는 긴 고리도 잡는다."""
    bd = Diagram()
    g1 = bd.add(Gain(1.0, name="g1"))
    g2 = bd.add(Gain(1.0, name="g2"))
    g3 = bd.add(Gain(1.0, name="g3"))
    bd.connect(g1, g2); bd.connect(g2, g3); bd.connect(g3, g1)
    with pytest.raises(AlgebraicLoopError):
        bd.compile()


def test_no_loop_still_orders_correctly():
    """[모델 5] 고리 없는 평범한 체인은 그대로 위상 정렬."""
    bd = Diagram()
    c = bd.add(Constant(1.0, name="c"))
    g = bd.add(Gain(2.0, name="g"))
    sc = bd.add(Scope(name="sc"))
    bd.connect(c, g); bd.connect(g, sc)
    pos = {b: i for i, b in enumerate(bd.compile())}
    assert pos[c] < pos[g] < pos[sc]
