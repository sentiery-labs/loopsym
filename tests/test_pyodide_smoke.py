"""Pyodide 단일 엔진 스모크 테스트 (구 test_viewer_sync 대체).

JS 시뮬 엔진 복제본은 폐기되었다 — 뷰어는 Pyodide 로 파이썬 엔진을 그대로
돌린다. 여기서는 뷰어와 동일한 경로(엔진 소스를 Pyodide FS 에 쓰고
webapi.run_simulation 호출)를 node 로 헤드리스 실행해서:
  1. 네이티브 파이썬 엔진과 결과가 일치하고
  2. 회귀 기준값(ex1/ex2/ex4)과 6자리 일치
함을 확인한다.

요구사항: node + pyodide npm 패키지 (repo 루트에서 `npm install`).
없으면 skip — CI 에서는 항상 실행된다.
"""

import json
import os
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blocksim import (            # noqa: E402
    Diagram, DiscreteIntegrator, Gain, Inport, Integrator, Outport,
    PyFunction, Scope, Step, Subsystem, Sum, TransferFunction,
    export_json, run, run_simulation,
)

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
HARNESS = os.path.join(HERE, "pyodide_smoke.mjs")

# 회귀 기준값 (WORKPLAN §6-3 — 뷰어/엔진 공통 계약)
EX1_Y10 = 1.000189      # ex1 PI 폐루프 y(10s)
EX2_TH8 = 0.306499      # ex2 진자 θ(8s)
EX4_Y10 = 1.000087      # ex4 이산 PI(Ts=0.01 기준 케이스) y(10s)

node = shutil.which("node")


def _pyodide_available():
    if node is None:
        return False
    r = subprocess.run(
        [node, "-e", "import('pyodide').then(()=>process.exit(0),()=>process.exit(1))"],
        cwd=ROOT, capture_output=True, timeout=60)
    return r.returncode == 0


pytestmark = pytest.mark.skipif(
    not _pyodide_available(),
    reason="node/pyodide 없음 — repo 루트에서 `npm install` 후 실행 (CI 는 항상 실행)")


# ---------------------------------------------------------------- 모델 3종
def ex1_pi_loop():
    bd = Diagram()
    ref = bd.add(Step(t_on=1.0, height=1.0, name="ref"))
    err = bd.add(Sum("+-", name="err"))
    kp = bd.add(Gain(k=3.0, name="Kp"))
    integ = bd.add(Integrator(name="err_int"))
    ki = bd.add(Gain(k=2.0, name="Ki"))
    pi = bd.add(Sum("++", name="PI"))
    plant = bd.add(TransferFunction([1], [1, 2, 1], name="plant"))
    sc = bd.add(Scope(n_in=2, labels=["ref", "y"], name="scope"))
    bd.connect(ref, err[0]); bd.connect(plant, err[1])
    bd.connect(err, kp); bd.connect(err, integ); bd.connect(integ, ki)
    bd.connect(kp, pi[0]); bd.connect(ki, pi[1]); bd.connect(pi, plant)
    bd.connect(ref, sc[0]); bd.connect(plant, sc[1])
    return bd, 10.0, 0.01


def ex2_pendulum():
    bd = Diagram()
    ref = bd.add(Step(t_on=1.0, height=0.8, name="ref"))
    ctrl = bd.add(PyFunction("6.0*(u0-u1) - 2.0*u2", n_in=3, name="PD_ctrl"))
    dyn = bd.add(PyFunction("-(9.81/1.0)*sin(u0) - 0.3*u1 + u2", n_in=3, name="pendulum"))
    omega = bd.add(Integrator(name="omega"))
    theta = bd.add(Integrator(name="theta"))
    sc = bd.add(Scope(n_in=2, labels=["ref", "theta"], name="scope"))
    bd.connect(ref, ctrl[0]); bd.connect(theta, ctrl[1]); bd.connect(omega, ctrl[2])
    bd.connect(theta, dyn[0]); bd.connect(omega, dyn[1]); bd.connect(ctrl, dyn[2])
    bd.connect(dyn, omega); bd.connect(omega, theta)
    bd.connect(ref, sc[0]); bd.connect(theta, sc[1])
    return bd, 8.0, 0.005


def ex3_masked_subsystem():
    inner = Diagram()
    e = inner.add(Inport(0, name="e"))
    kp = inner.add(Gain(k="$Kp", name="Kp"))
    it = inner.add(Integrator(name="err_int"))
    ki = inner.add(Gain(k="$Ki", name="Ki"))
    add = inner.add(Sum("++", name="add"))
    u = inner.add(Outport(0, name="u"))
    inner.connect(e, kp); inner.connect(e, it); inner.connect(it, ki)
    inner.connect(kp, add[0]); inner.connect(ki, add[1]); inner.connect(add, u)
    bd = Diagram()
    ref = bd.add(Step(t_on=1.0, name="ref"))
    err = bd.add(Sum("+-", name="err"))
    ctrl = bd.add(Subsystem(inner, params={"Kp": 3.0, "Ki": 2.0}, name="PI_ctrl"))
    plant = bd.add(TransferFunction([1], [1, 2, 1], name="plant"))
    sc = bd.add(Scope(n_in=2, labels=["ref", "y"], name="scope"))
    bd.connect(ref, err[0]); bd.connect(plant, err[1])
    bd.connect(err, ctrl); bd.connect(ctrl, plant)
    bd.connect(ref, sc[0]); bd.connect(plant, sc[1])
    return bd, 10.0, 0.01


def ex4_discrete_pi():
    bd = Diagram()
    ref = bd.add(Step(t_on=1.0, name="ref"))
    err = bd.add(Sum("+-", name="err"))
    kp = bd.add(Gain(3.0, name="Kp"))
    integ = bd.add(DiscreteIntegrator(st=0.01, name="dint"))
    ki = bd.add(Gain(2.0, name="Ki"))
    add = bd.add(Sum("++", name="PI"))
    plant = bd.add(TransferFunction([1], [1, 2, 1], name="plant"))
    sc = bd.add(Scope(n_in=1, labels=["y"], name="scope"))
    bd.connect(ref, err[0]); bd.connect(plant, err[1])
    bd.connect(err, kp); bd.connect(err, integ); bd.connect(integ, ki)
    bd.connect(kp, add[0]); bd.connect(ki, add[1]); bd.connect(add, plant)
    bd.connect(plant, sc)
    return bd, 10.0, 0.01


CASES = {"ex1": (ex1_pi_loop, "scope", 1, EX1_Y10),
         "ex2": (ex2_pendulum, "scope", 1, EX2_TH8),
         "ex3": (ex3_masked_subsystem, "scope", 1, EX1_Y10),   # ex1 과 같은 PI = 같은 응답
         "ex4": (ex4_discrete_pi, "scope", 0, EX4_Y10)}


def test_pyodide_matches_python_engine(tmp_path):
    """뷰어 실행 경로(Pyodide + run_simulation) = 네이티브 파이썬 엔진 = 회귀 기준값."""
    cases, py_ref = [], {}
    for name, (build, scope_name, ch, expect) in CASES.items():
        bd, t_end, dt = build()
        cases.append({"name": name, "model": export_json(bd), "t_end": t_end, "dt": dt})
        run(bd, t_end, dt)     # 네이티브 엔진 기준값
        sc = [b for b in bd.blocks if isinstance(b, Scope)][0]
        py_ref[name] = sc.data[ch][-1]
        assert py_ref[name] == pytest.approx(expect, abs=5e-7), f"{name}: 네이티브 엔진이 회귀 기준값과 다름"

    cf = tmp_path / "cases.json"
    cf.write_text(json.dumps(cases), encoding="utf-8")
    env = dict(os.environ, BS_SRC_DIR=os.path.join(ROOT, "blocksim"), BS_CASES=str(cf))
    out = subprocess.run([node, HARNESS], env=env, cwd=ROOT,
                         capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr
    results = {r["name"]: r["result"] for r in json.loads(out.stdout)}

    for name, (build, scope_name, ch, expect) in CASES.items():
        res = results[name]
        assert res["errors"] == [], f"{name}: {res['errors']}"
        disp = [d for d in res["signals"] if d.endswith(scope_name)][0]
        last = res["signals"][disp][ch][-1]
        assert last == pytest.approx(py_ref[name], abs=1e-9), \
            f"{name}: pyodide={last} python={py_ref[name]}"


def test_pyodide_reports_errors(tmp_path):
    """엔진 에러(대수 루프)가 errors 배열로 돌아오는지 — 뷰어 상태줄 경로.

    export_json 은 자동배치에 compile() 을 쓰므로 잘못된 모델은 뷰어가
    만들 JSON 그대로 손으로 적는다 (뷰어에서는 그리기만 하면 만들어짐)."""
    model = {"blocks": [
        {"id": 0, "type": "Gain", "name": "g1", "params": {"k": 2.0}, "x": 0, "y": 0},
        {"id": 1, "type": "Gain", "name": "g2", "params": {"k": 0.4}, "x": 0, "y": 0},
        {"id": 2, "type": "Scope", "name": "sc", "params": {"n_in": 1, "labels": ["in0"]}, "x": 0, "y": 0},
    ], "wires": [
        {"src": [0, 0], "dst": [1, 0]}, {"src": [1, 0], "dst": [0, 0]},
        {"src": [1, 0], "dst": [2, 0]},
    ]}
    cf = tmp_path / "cases.json"
    cf.write_text(json.dumps([{"name": "loop", "model": model,
                               "t_end": 1.0, "dt": 0.01}]), encoding="utf-8")
    env = dict(os.environ, BS_SRC_DIR=os.path.join(ROOT, "blocksim"), BS_CASES=str(cf))
    out = subprocess.run([node, HARNESS], env=env, cwd=ROOT,
                         capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr
    res = json.loads(out.stdout)[0]["result"]
    assert res["errors"] and "대수 루프" in res["errors"][0]


def test_run_simulation_direct():
    """node 없이도 도는 최소 검증 — run_simulation 자체의 계약 (JSON in/out)."""
    bd, t_end, dt = ex1_pi_loop()
    res = json.loads(run_simulation(json.dumps(export_json(bd)), t_end, dt))
    assert res["errors"] == []
    assert res["signals"]["scope"][1][-1] == pytest.approx(EX1_Y10, abs=5e-7)
    assert len(res["time"]) == round(t_end / dt) + 1
    assert res["labels"]["scope"] == ["ref", "y"]


def test_viewer_has_no_js_engine():
    """AC: viewer.html 에 시뮬레이션 로직 JS 0줄 — 폐기된 엔진 심볼이 없어야 한다."""
    src = open(os.path.join(ROOT, "blocksim", "viewer.html"), encoding="utf-8").read()
    for sym in ["makeRuntime", "compileFlat", "flattenModel", "resolveMask", "compileExpr"]:
        assert sym not in src, f"폐기된 JS 엔진 심볼 잔존: {sym}"
    assert "run_simulation" in src   # Pyodide 경로는 있어야 함
