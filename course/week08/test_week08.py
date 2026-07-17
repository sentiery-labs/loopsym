"""8주차 채점기 — 개루프 호버 — 추력 손 계산이 맞으면 떨어지지 않는다

제출물: week08_model.json (뷰어에서 완성해 '저장' 으로 덮어쓰기).
채점: python -m pytest test_week08.py -q
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
MODEL = os.path.join(HERE, "week08_model.json")


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


def test_plant_present_and_all_motors_wired():
    j = _model()
    plants = _blocks(j, "QuadPlant")
    assert plants, "QuadPlant 블록이 없다"
    pid = plants[0]["id"]
    for i in range(4):
        assert any(w["dst"] == [pid, i] for w in j["wires"]), \
            f"모터 입력 m{i+1} 이 연결되지 않음"


def test_hover_thrust_keeps_altitude():
    """cmd=mg/(N·kF)=0.5 면 3초 뒤에도 고도 5m 근방이어야 한다."""
    sc = _run(3.0)
    alt = sc["scope_pos"].data[2][-1]
    assert math.isfinite(alt)
    assert abs(alt + 5.0) < 0.2, \
        f"3초 뒤 고도 {-alt:.1f}m — 호버 추력(손 계산)을 다시 확인"


def test_level_attitude_maintained():
    sc = _run(3.0)
    assert sc["scope_att"].data[0][-1] > 0.999, "자세가 뒤집히고 있다"
