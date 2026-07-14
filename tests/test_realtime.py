"""실시간 모드 [CLD-P42] 테스트.

1. run_realtime 이 벽시계에 페이싱되고, 수치는 배치 run() 과 완전히 같다
2. stop_event 가 스텝 경계에서 즉시 반영된다
3. 서버 mode="realtime" — 라이브 스트리밍(완주 전에 progress 도착) + 지터 통계
"""

import json
import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blocksim import (            # noqa: E402
    Diagram, DiscreteIntegrator, Gain, Scope, Step, Sum, TransferFunction,
    export_json, run, run_realtime,
)

DT = 0.02      # 50Hz


def pi_loop():
    bd = Diagram()
    ref = bd.add(Step(t_on=0.2, name="ref"))
    err = bd.add(Sum("+-", name="err"))
    kp = bd.add(Gain(3.0, name="Kp"))
    integ = bd.add(DiscreteIntegrator(st=DT, name="dint"))
    ki = bd.add(Gain(2.0, name="Ki"))
    add = bd.add(Sum("++", name="PI"))
    plant = bd.add(TransferFunction([1], [1, 2, 1], name="plant"))
    sc = bd.add(Scope(n_in=1, labels=["y"], name="scope"))
    bd.connect(ref, err[0]); bd.connect(plant, err[1])
    bd.connect(err, kp); bd.connect(err, integ); bd.connect(integ, ki)
    bd.connect(kp, add[0]); bd.connect(ki, add[1]); bd.connect(add, plant)
    bd.connect(plant, sc)
    return bd, sc


def test_realtime_paces_and_matches_sim():
    """벽시계 1초에 맞춰 돌고, 수치는 배치 실행과 비트 단위로 같다."""
    bd_ref, sc_ref = pi_loop()
    run(bd_ref, 1.0, DT)                       # 배치 기준

    bd, sc = pi_loop()
    ticks = []
    t0 = time.perf_counter()
    stats = run_realtime(bd, 1.0, DT, on_step=lambda s, t: ticks.append(t))
    wall = time.perf_counter() - t0

    assert 0.9 <= wall <= 1.6, f"벽시계 페이싱 실패: {wall:.2f}s"
    assert stats["steps"] == round(1.0 / DT)   # 간격 수 = 스텝 수 - 1
    assert len(ticks) == round(1.0 / DT) + 1
    assert sc.data[0] == sc_ref.data[0], "실시간 페이싱이 수치를 바꿈"
    for k in ("p50", "p95", "p99", "max", "miss_pct", "burst", "period_ms"):
        assert k in stats


def test_realtime_speed_factor():
    """speed=4 배속이면 벽시계 시간이 1/4."""
    bd, _ = pi_loop()
    t0 = time.perf_counter()
    run_realtime(bd, 1.0, DT, speed=4.0)
    assert time.perf_counter() - t0 < 0.6


def test_realtime_stop_event():
    bd, _ = pi_loop()
    stop = threading.Event()
    threading.Timer(0.3, stop.set).start()
    t0 = time.perf_counter()
    stats = run_realtime(bd, 60.0, DT, stop_event=stop)
    assert time.perf_counter() - t0 < 1.0
    assert stats["stopped"] is True
    assert stats["steps"] < 60.0 / DT


# ---------------------------------------------------------------- 서버 realtime 모드
pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")
ws_sync = pytest.importorskip("websockets.sync.client")

from tests.test_server import server            # noqa: E402,F401  (fixture 재사용)


def test_server_realtime_mode_streams_live(server):
    """mode=realtime: 완주 전에 progress 가 오고(라이브), done 은 벽시계 뒤, timing 포함."""
    bd, sc = pi_loop()
    model = export_json(bd)
    run(bd, 1.5, DT)                            # 네이티브 기준

    t0 = time.monotonic()
    first_progress = None
    accum = []
    with ws_sync.connect(server) as ws:
        ws.send(json.dumps({"cmd": "run", "diagram": model,
                            "t_end": 1.5, "dt": DT, "mode": "realtime"}))
        while True:
            m = json.loads(ws.recv(timeout=15))
            if m["type"] == "progress":
                if first_progress is None and m["signals_chunk"]["time"]:
                    first_progress = time.monotonic() - t0
                for k, chans in m["signals_chunk"]["signals"].items():
                    accum += chans[0]
            elif m["type"] == "done":
                break
            else:
                raise AssertionError(m.get("message"))
    wall = time.monotonic() - t0

    assert first_progress is not None and first_progress < 1.0, \
        f"라이브 스트리밍 아님 (첫 청크 {first_progress}s)"
    assert wall >= 1.3, f"벽시계 페이싱 안 됨: {wall:.2f}s"
    assert m["stats"]["mode"] == "realtime"
    assert "timing" in m["stats"] and "p99" in m["stats"]["timing"]
    assert accum[-1] == pytest.approx(sc.data[0][-1], abs=1e-9), "sim 모드와 수치 불일치"


def test_server_sim_mode_has_no_timing(server):
    """기본 sim 모드는 페이싱 없이 즉시 끝나고 timing 이 없다."""
    bd, _ = pi_loop()
    with ws_sync.connect(server) as ws:
        ws.send(json.dumps({"cmd": "run", "diagram": export_json(bd),
                            "t_end": 1.5, "dt": DT}))
        t0 = time.monotonic()
        while True:
            m = json.loads(ws.recv(timeout=15))
            if m["type"] == "done":
                break
    assert time.monotonic() - t0 < 1.0
    assert m["stats"]["mode"] == "sim" and "timing" not in m["stats"]
