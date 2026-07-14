"""PyFunction 문장형(여러 줄) 코드 지원 테스트 — 뷰어 코드 편집기의 엔진 짝.

한 줄이면 식(eval), 여러 줄이면 문장(exec)으로 실행되고 출력은
y (단일) 또는 y0..y{n_out-1} 대입 규약을 따른다.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loopsym import (            # noqa: E402
    Constant, Diagram, PyFunction, Scope, export_json, load_json, run,
    run_simulation,
)


def _run_single(block, t_end=0.1, dt=0.05, n_src=1):
    bd = Diagram()
    srcs = [bd.add(Constant(v)) for v in (2.0, 5.0, -1.0)[:n_src]]
    b = bd.add(block)
    sc = bd.add(Scope(n_in=b.n_out, name="sc"))
    for i, s in enumerate(srcs):
        bd.connect(s, b[i])
    for i in range(b.n_out):
        bd.connect(b[i], sc[i])
    run(bd, t_end, dt)
    return [d[-1] for d in sc.data]


def test_expr_single_line_unchanged():
    assert _run_single(PyFunction("3.0*u0 + 1.0", n_in=1)) == [7.0]


def test_exec_multiline_single_output_y():
    code = "e = u0 * 2\nif e > 3:\n    e = e + 0.5\ny = e"
    assert _run_single(PyFunction(code, n_in=1)) == [4.5]


def test_exec_multiline_multi_output():
    code = "e = u0 - u1\ny0 = 3*e\ny1 = 2*e"
    assert _run_single(PyFunction(code, n_in=2, n_out=2), n_src=2) == [-9.0, -6.0]


def test_exec_missing_output_raises():
    with pytest.raises(ValueError, match="y1"):
        _run_single(PyFunction("y0 = u0", n_in=1, n_out=2))


def test_exec_comprehension_sees_inputs():
    # exec 를 globals 로 실행하는 이유 — locals 분리면 컴프리헨션이 u0 를 못 본다
    code = "y = sum([u0 * k for k in [1, 2, 3]])"
    assert _run_single(PyFunction(code, n_in=1)) == [12.0]


def test_exec_json_roundtrip_and_webapi():
    """여러 줄 expr 이 저장/열기(JSON)와 run_simulation 경로를 통과한다."""
    bd = Diagram()
    c = bd.add(Constant(4.0, name="c"))
    f = bd.add(PyFunction("e = u0/2\ny = e + 1", n_in=1, name="f"))
    sc = bd.add(Scope(name="sc"))
    bd.connect(c, f); bd.connect(f, sc)
    j = json.loads(json.dumps(export_json(bd)))

    bd2 = load_json(j)
    run(bd2, 0.1, 0.05)
    sc2 = [b for b in bd2.blocks if isinstance(b, Scope)][0]
    assert sc2.data[0][-1] == 3.0

    res = json.loads(run_simulation(json.dumps(j), 0.1, 0.05))
    assert res["errors"] == [] and res["signals"]["sc"][0][-1] == 3.0
