"""파이썬 엔진 ↔ 뷰어 JS 엔진 동기화 계약 테스트 (WORKPLAN §6-3).

같은 모델을 양쪽에서 돌려 Scope 마지막 값이 일치하는지 확인한다.
node 가 없으면 skip.
"""

import json
import os
import re
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blocksim import (            # noqa: E402
    Diagram, DiscreteIntegrator, Gain, Inport, Integrator, Outport,
    PyFunction, Scope, Step, Subsystem, Sum, TransferFunction, UnitDelay,
    export_json, run,
)

HERE = os.path.dirname(__file__)
VIEWER = os.path.join(HERE, "..", "blocksim", "viewer.html")

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node 없음 — JS 동기화 테스트 skip")


def run_js(model_json, t_end, dt, tmp_path):
    """viewer.html 의 스크립트를 stubs + runner 와 합쳐 node 로 실행."""
    src = open(VIEWER, encoding="utf-8").read()
    script = re.search(r"<script>(.*)</script>", src, re.S).group(1)
    stubs = open(os.path.join(HERE, "js_harness", "stubs.js"), encoding="utf-8").read()
    runner = open(os.path.join(HERE, "js_harness", "runner.js"), encoding="utf-8").read()
    js = tmp_path / "harness.js"
    js.write_text(stubs + script + runner, encoding="utf-8")
    mj = tmp_path / "model.json"
    mj.write_text(json.dumps(model_json), encoding="utf-8")
    env = dict(os.environ, BS_MODEL=str(mj), BS_TEND=str(t_end), BS_DT=str(dt))
    out = subprocess.run([node, str(js)], env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def compare(bd, t_end, dt, tmp_path):
    j = export_json(bd)
    run(bd, t_end, dt)
    py_last = {}
    for b in bd.blocks:
        if isinstance(b, Scope):
            py_last[b.name] = [d[-1] for d in b.data]
    res = run_js(j, t_end, dt, tmp_path)
    assert res["status"][1] == "ok", res["status"][0]
    for s in res["scopes"]:
        name = s["disp"].split("/")[-1]
        for a, b_ in zip(py_last[name], s["last"]):
            assert a == pytest.approx(b_, abs=1e-9), f"{name}: py={a} js={b_}"


def test_sync_masked_pi_subsystem(tmp_path):
    inner = Diagram()
    e = inner.add(Inport(0)); kp = inner.add(Gain(k="$Kp", name="Kp"))
    it = inner.add(Integrator()); ki = inner.add(Gain(k="$Ki", name="Ki"))
    add = inner.add(Sum("++")); o = inner.add(Outport(0))
    inner.connect(e, kp); inner.connect(e, it); inner.connect(it, ki)
    inner.connect(kp, add[0]); inner.connect(ki, add[1]); inner.connect(add, o)

    bd = Diagram()
    ref = bd.add(Step(t_on=1.0, name="ref")); err = bd.add(Sum("+-"))
    ctrl = bd.add(Subsystem(inner, params={"Kp": 3.0, "Ki": 2.0}, name="PI"))
    plant = bd.add(TransferFunction([1], [1, 2, 1])); sc = bd.add(Scope(n_in=2, name="sc"))
    bd.connect(ref, err[0]); bd.connect(plant, err[1])
    bd.connect(err, ctrl); bd.connect(ctrl, plant)
    bd.connect(ref, sc[0]); bd.connect(plant, sc[1])
    compare(bd, 10.0, 0.01, tmp_path)


def test_sync_discrete_blocks(tmp_path):
    bd = Diagram()
    ref = bd.add(Step(t_on=1.0)); err = bd.add(Sum("+-"))
    kp = bd.add(Gain(3.0)); di = bd.add(DiscreteIntegrator(st=0.02)); ki = bd.add(Gain(2.0))
    add = bd.add(Sum("++")); ud = bd.add(UnitDelay(st=0.02))
    plant = bd.add(TransferFunction([1], [1, 2, 1])); sc = bd.add(Scope(n_in=1, name="sc"))
    bd.connect(ref, err[0]); bd.connect(plant, err[1])
    bd.connect(err, kp); bd.connect(err, di); bd.connect(di, ki)
    bd.connect(kp, add[0]); bd.connect(ki, add[1]); bd.connect(add, ud)
    bd.connect(ud, plant); bd.connect(plant, sc)
    compare(bd, 10.0, 0.01, tmp_path)


def test_sync_pyfunction_pendulum(tmp_path):
    bd = Diagram()
    ref = bd.add(Step(t_on=1.0, height=0.8))
    ctrl = bd.add(PyFunction("6.0*(u0-u1) - 2.0*u2", n_in=3))
    dyn = bd.add(PyFunction("-(9.81/1.0)*sin(u0) - 0.3*u1 + u2", n_in=3))
    om = bd.add(Integrator()); th = bd.add(Integrator()); sc = bd.add(Scope(name="sc"))
    bd.connect(ref, ctrl[0]); bd.connect(th, ctrl[1]); bd.connect(om, ctrl[2])
    bd.connect(th, dyn[0]); bd.connect(om, dyn[1]); bd.connect(ctrl, dyn[2])
    bd.connect(dyn, om); bd.connect(om, th); bd.connect(th, sc)
    compare(bd, 8.0, 0.005, tmp_path)
