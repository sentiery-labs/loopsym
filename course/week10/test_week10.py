"""10주차 채점기 — 호버 폐루프 완성 — 드론이 처음 뜨는 주

제출물: week10_model.json (뷰어에서 완성해 '저장' 으로 덮어쓰기).
채점: python -m pytest test_week10.py -q
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
MODEL = os.path.join(HERE, "week10_model.json")


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


def test_cascade_wired():
    """캐스케이드: pos→att(att_cmd), att→rate(rate_sp), pos→mixer(thrust)."""
    j = _model()
    pos = _blocks(j, "PositionController")
    att = _blocks(j, "AttitudeController")
    rate = _blocks(j, "RateController")
    mix = _blocks(j, "Mixer") + _blocks(j, "QuadXMixer")
    assert pos and att and rate and mix, "캐스케이드 블록(위치/자세/각속도/믹서)이 다 있어야 한다"
    pid, aid, rid, mid = pos[0]["id"], att[0]["id"], rate[0]["id"], mix[0]["id"]
    for i in range(3):
        assert _wired(j, pid, i, aid, 4 + i), f"att_cmd {i} (pos→att) 미연결"
        assert _wired(j, aid, i, rid, i), f"rate_sp {i} (att→rate) 미연결"
    assert _wired(j, pid, 3, mid, 3), "thrust (pos→mixer) 미연결"


def test_position_mission():
    """북 2m + 고도 6m 이동 후 정지 호버."""
    sc = _run(8.0)
    n, e, d = (ch[-1] for ch in sc["scope_pos"].data)
    assert abs(n - 2.0) < 0.1 and abs(e) < 0.1 and abs(d + 6.0) < 0.1, \
        f"최종 NED=[{n:.2f},{e:.2f},{d:.2f}] — 목표 [2,0,-6]"


def test_settled():
    sc = _run(8.0)
    ch = sc["scope_pos"].data[0]
    assert abs(ch[-1] - ch[-125]) < 0.02, "정착하지 않고 계속 움직인다"
