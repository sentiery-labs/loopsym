"""11주차 채점기 — ideal → noisy — 센서가 완벽하다는 거짓말

제출물: week11_model.json (뷰어에서 완성해 '저장' 으로 덮어쓰기).
채점: python -m pytest test_week11.py -q
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
MODEL = os.path.join(HERE, "week11_model.json")


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


def test_imu_present_and_noisy():
    j = _model()
    imus = _blocks(j, "IMU")
    assert imus, "IMU 블록이 없다 — 10주차 다이어그램에 IMU 를 삽입하라"
    assert imus[0]["params"].get("fidelity") == "noisy", \
        "fidelity 드롭다운을 'noisy' 로 — 이 한 클릭이 이번 주의 전부다"


def test_rate_feedback_through_imu():
    """rate 피드백이 참값이 아니라 IMU gyro 를 경유해야 한다."""
    j = _model()
    iid = _blocks(j, "IMU")[0]["id"]
    rid = _blocks(j, "RateController")[0]["id"]
    for i in range(3):
        assert _wired(j, iid, i, rid, 3 + i), \
            f"rate 피드백 {'pqr'[i]} 가 IMU gyro 를 경유하지 않음"


def test_mission_still_passes_with_noise():
    """noisy(바이어스+잡음)여도 미션은 성립해야 한다 (시드 고정)."""
    sc = _run(8.0)
    n, e, d = (ch[-1] for ch in sc["scope_pos"].data)
    assert all(math.isfinite(v) for ch in sc["scope_pos"].data for v in ch)
    assert abs(n - 2.0) < 0.15 and abs(e) < 0.15 and abs(d + 6.0) < 0.15, \
        f"최종 NED=[{n:.2f},{e:.2f},{d:.2f}] — noisy 에서 미션 실패"
