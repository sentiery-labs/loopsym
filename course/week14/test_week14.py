"""14주차 채점기 — 같은 다이어그램, 다른 기체 — 기체를 바꿔도 미션은 완주된다

제출물: week14_model.json (뷰어에서 완성해 '저장' 으로 덮어쓰기).
채점: python -m pytest test_week14.py -q
"""

import json
import math
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))

from loopsym import Simulator, load_json                  # noqa: E402

DT = 0.004
MODEL = os.path.join(HERE, "week14_model.json")


def _model():
    with open(MODEL, encoding="utf-8") as f:
        return json.load(f)


def _run(T, j=None):
    bd = load_json(j if j is not None else _model())
    sim = Simulator(bd)
    sim.run(T, DT)
    return {b.name: b for b in sim.bd.blocks if type(b).__name__ == "Scope"}


def _blocks(j, typ):
    return [b for b in j["blocks"] if b["type"] == typ]


def _wired(j, src_id, src_port, dst_id, dst_port):
    return any(w["src"] == [src_id, src_port] and w["dst"] == [dst_id, dst_port]
               for w in j["wires"])


def _heavy(j):
    """채점기가 기체를 +30% 무겁게 바꾼다 — fidelity 사다리의 소프트웨어판."""
    import copy
    j = copy.deepcopy(j)
    for b in j["blocks"]:
        if b["type"] == "QuadPlant":
            b["params"]["m"] = 1.3
    return j


def test_mission_on_heavier_vehicle():
    sc = _run(20.0, _heavy(_model()))
    idx = sc["scope_wp"].data[0][-1]
    n, e, d = (ch[-1] for ch in sc["scope_pos"].data)
    assert idx >= 3, f"무거운 기체에서 방문 {int(idx)}/3 — 튜닝 여유 부족"
    assert abs(n) < 0.2 and abs(e) < 0.2 and abs(d + 5.0) < 0.2


def test_original_vehicle_still_passes():
    sc = _run(16.0)
    assert sc["scope_wp"].data[0][-1] >= 3
