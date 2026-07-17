"""15주차 채점기 — 종합 프로젝트 자동 채점분 — noisy 센서 + 필터 + 미션 전부

제출물: week15_model.json (뷰어에서 완성해 '저장' 으로 덮어쓰기).
채점: python -m pytest test_week15.py -q
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
MODEL = os.path.join(HERE, "week15_model.json")


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


def test_full_chain_structure():
    """신호사슬 완성: 센서(noisy) → 추정(CF) → 제어 → 할당 → 플랜트 + 항법."""
    j = _model()
    assert _blocks(j, "IMU"), "IMU 없음"
    assert _blocks(j, "IMU")[0]["params"].get("fidelity") == "noisy", "IMU 는 noisy"
    assert _blocks(j, "ComplementaryFilter"), "ComplementaryFilter 없음"
    assert _blocks(j, "WaypointManager"), "WaypointManager 없음"
    iid = _blocks(j, "IMU")[0]["id"]
    cid = _blocks(j, "ComplementaryFilter")[0]["id"]
    rid = _blocks(j, "RateController")[0]["id"]
    for i in range(3):
        assert _wired(j, cid, 4 + i, rid, 3 + i), "rate 피드백은 CF omega_est 경유"
    for i in range(6):
        assert _wired(j, iid, i, cid, i), "IMU → CF 배선"


def test_full_mission():
    sc = _run(20.0)
    idx = sc["scope_wp"].data[0][-1]
    n, e, d = (ch[-1] for ch in sc["scope_pos"].data)
    assert all(math.isfinite(v) for ch in sc["scope_pos"].data for v in ch)
    assert idx >= 3, f"방문 {int(idx)}/3"
    assert abs(n) < 0.2 and abs(e) < 0.2 and abs(d + 5.0) < 0.2, \
        f"최종 NED=[{n:.2f},{e:.2f},{d:.2f}]"
