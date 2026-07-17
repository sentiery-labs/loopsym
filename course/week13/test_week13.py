"""13주차 채점기 — 웨이포인트 미션 — 항법 계층

제출물: week13_model.json (뷰어에서 완성해 '저장' 으로 덮어쓰기).
채점: python -m pytest test_week13.py -q
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
MODEL = os.path.join(HERE, "week13_model.json")


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


def test_wp_manager_wired():
    j = _model()
    wps = _blocks(j, "WaypointManager")
    assert wps, "WaypointManager 블록이 없다"
    wid = wps[0]["id"]
    pid = _blocks(j, "QuadPlant")[0]["id"]
    cid = _blocks(j, "PositionController")[0]["id"]
    for i in range(3):
        assert _wired(j, pid, 7 + i, wid, i), f"현재 위치 {'NED'[i]} → wp 미연결"
        assert _wired(j, wid, i, cid, i), f"pos_sp {'NED'[i]} (wp→pos_ctrl) 미연결"


def test_mission_visits_all_waypoints():
    sc = _run(16.0)
    idx = sc["scope_wp"].data[0][-1]
    assert idx >= 3, f"방문한 웨이포인트 {int(idx)}/3 — 순회 미완"


def test_returns_to_final_waypoint():
    sc = _run(16.0)
    n, e, d = (ch[-1] for ch in sc["scope_pos"].data)
    assert abs(n) < 0.15 and abs(e) < 0.15 and abs(d + 5.0) < 0.15, \
        f"최종 NED=[{n:.2f},{e:.2f},{d:.2f}] — 마지막 웨이포인트 [0,0,-5] 미도달"
