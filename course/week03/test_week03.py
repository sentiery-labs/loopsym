"""3주차 채점기 — Sum/Product/PyFunction 을 loopsym 오라클과 대조."""

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", ".."))

import myblocks as mb                                   # noqa: E402
import loopsym as bs                                   # noqa: E402


@pytest.mark.parametrize("signs,u", [
    ("+-", (3.0, 1.2)),
    ("+--", (1.0, 2.0, 3.5)),
    ("++++", (0.1, 0.2, 0.3, 0.4)),
    ("-", (7.0,)),
])
def test_sum_matches_oracle(signs, u):
    mine, oracle = mb.Sum(signs), bs.Sum(signs)
    assert mine.n_in == len(signs)
    assert mine.output(0.0, u, ()) == (oracle.output(0.0, u, ())[0],)


def test_sum_rejects_bad_signs():
    with pytest.raises(ValueError):
        mb.Sum("+x")


@pytest.mark.parametrize("ops,u", [
    ("**", (3.0, 4.0)),
    ("*/", (10.0, 4.0)),
    ("*//", (24.0, 2.0, 3.0)),
])
def test_product_matches_oracle(ops, u):
    mine, oracle = mb.Product(ops), bs.Product(ops)
    assert mine.n_in == len(ops)
    assert mine.output(0.0, u, ()) == (oracle.output(0.0, u, ())[0],)


def test_product_rejects_bad_ops():
    with pytest.raises(ValueError):
        mb.Product("*+")


@pytest.mark.parametrize("expr,n_in,u,t", [
    ("3.0*u0 + 1.0", 1, (2.0,), 0.0),
    ("6.0*(u0-u1) - 2.0*u2", 3, (0.8, 0.3, 0.1), 0.0),
    ("sin(t) + u0", 1, (1.0,), 0.7),
    ("min(2.0, sqrt(u0**2 + u1**2))", 2, (3.0, 4.0), 0.0),
])
def test_pyfunction_matches_oracle(expr, n_in, u, t):
    mine, oracle = mb.PyFunction(expr, n_in=n_in), bs.PyFunction(expr, n_in=n_in)
    assert abs(mine.output(t, u, ())[0] - oracle.output(t, u, ())[0]) < 1e-12


def test_pyfunction_tuple_output():
    f = mb.PyFunction("(u0 + 1.0, u0 - 1.0)", n_in=1, n_out=2)
    assert f.output(0.0, (2.0,), ()) == (3.0, 1.0)


def test_pyfunction_is_sandboxed():
    """식 안에서 __builtins__ 접근이 막혀 있어야 한다 (안전 환경)."""
    f = mb.PyFunction("open('x')", n_in=0)
    with pytest.raises(Exception):
        f.output(0.0, (), ())
