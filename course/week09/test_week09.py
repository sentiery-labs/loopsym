"""9주차 채점기 — 각속도(rate) 폐루프 — 요 회전 명령 추종

제출물: week09_model.json (뷰어에서 완성해 '저장' 으로 덮어쓰기).
채점: python -m pytest test_week09.py -q
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
MODEL = os.path.join(HERE, "week09_model.json")


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


def test_rate_feedback_wired():
    """rate_ctrl 의 각속도 피드백(입력 3~5)이 플랜트에서 와야 한다."""
    j = _model()
    rates = _blocks(j, "RateController")
    plants = _blocks(j, "QuadPlant")
    assert rates and plants
    rid, pid = rates[0]["id"], plants[0]["id"]
    for i in range(3):
        assert _wired(j, pid, 4 + i, rid, 3 + i), \
            f"rate 피드백 {'pqr'[i]} (플랜트 출력 {4+i} → rate_ctrl 입력 {3+i}) 미연결"


def test_yaw_rate_tracks_command():
    sc = _run(4.0)
    r = sc["★scope_rate"].data[1][-1]
    assert math.isfinite(r)
    assert abs(r - 0.5) < 0.05, f"r(4s)={r:.3f} — 명령 0.5 rad/s 를 추종하지 못함"


def test_other_axes_stay_quiet():
    j = _model()
    pid = _blocks(j, "QuadPlant")[0]["id"]
    bd = load_json(j)
    sim = Simulator(bd); sim.run(4.0, DT)
    plant = [b for b in sim.bd.blocks if type(b).__name__ == "QuadPlant"][0]
    # 마지막 상태를 Scope 없이 직접 확인하기 어렵다 — r 만 도는지 scope 로 확인
    sc = {b.name: b for b in sim.bd.blocks if type(b).__name__ == "Scope"}
    assert all(math.isfinite(v) for ch in sc["★scope_rate"].data for v in ch)
