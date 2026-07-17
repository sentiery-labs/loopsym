"""12주차 채점기 — 상보필터 — 바이어스를 추정해서 빼낸다

제출물: week12_model.json (뷰어에서 완성해 '저장' 으로 덮어쓰기).
채점: python -m pytest test_week12.py -q
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
MODEL = os.path.join(HERE, "week12_model.json")


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


def test_cf_present_and_wired():
    j = _model()
    cfs = _blocks(j, "ComplementaryFilter")
    assert cfs, "ComplementaryFilter 블록이 없다"
    cid = cfs[0]["id"]
    iid = _blocks(j, "IMU")[0]["id"]
    rid = _blocks(j, "RateController")[0]["id"]
    for i in range(6):
        assert _wired(j, iid, i, cid, i), f"IMU 출력 {i} → CF 입력 {i} 미연결"
    for i in range(3):
        assert _wired(j, cid, 4 + i, rid, 3 + i), \
            f"rate 피드백 {'pqr'[i]} 가 CF 의 보정 각속도(omega_est)를 경유하지 않음"


def test_mission_passes_with_cf():
    sc = _run(8.0)
    n, e, d = (ch[-1] for ch in sc["scope_pos"].data)
    assert abs(n - 2.0) < 0.15 and abs(e) < 0.15 and abs(d + 6.0) < 0.15


def test_cf_not_used_for_attitude():
    """(정직한 한계) CF 자세추정(q_est)을 자세 피드백에 직접 쓰면 비력
    특성으로 발산한다 — 이 다이어그램에서는 att 피드백이 참값이어야 한다.
    노트북 '이론' 절 참조 (EKF/GPS 결합이 필요한 이유)."""
    j = _model()
    cid = _blocks(j, "ComplementaryFilter")[0]["id"]
    aid = _blocks(j, "AttitudeController")[0]["id"]
    for i in range(4):
        assert not _wired(j, cid, i, aid, i), \
            "CF q_est 를 자세 피드백에 직접 쓰지 말 것 (노트북 이론 절)"
