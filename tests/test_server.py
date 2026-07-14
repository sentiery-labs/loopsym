"""로컬 서버 모드(blocksim/server.py) 통합 테스트.

실제로 `python -m blocksim.server` 서브프로세스를 띄우고 websockets
클라이언트(뷰어의 서버 모드와 같은 프로토콜)로:
  1. ex1~ex4 회귀 — 결과가 네이티브 엔진(= Pyodide 모드와 동일 코드)과 일치
  2. 시뮬레이션 중 stop 이 1초 안에 반영
을 확인한다. fastapi/uvicorn/websockets 없으면 skip.
"""

import json
import os
import socket
import subprocess
import sys
import time

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")
ws_sync = pytest.importorskip("websockets.sync.client")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blocksim import Scope, export_json, run          # noqa: E402
from tests.test_pyodide_smoke import CASES            # noqa: E402  (ex1~ex4 모델 공유)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="module")
def server():
    with socket.socket() as s:                 # 빈 포트 확보
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [sys.executable, "-m", "blocksim.server", "--port", str(port)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    url = f"ws://127.0.0.1:{port}/ws"
    try:
        for _ in range(100):                   # 기동 대기 (최대 10s)
            try:
                with ws_sync.connect(url, open_timeout=1):
                    break
            except OSError:
                if proc.poll() is not None:
                    raise RuntimeError("서버 조기 종료:\n" + proc.stdout.read())
                time.sleep(0.1)
        else:
            raise RuntimeError("서버가 10초 안에 뜨지 않음")
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def _run_via_server(url, model, t_end, dt, timeout=120):
    """뷰어의 서버 모드와 동일한 순서: run 전송 → progress 누적 → done."""
    accum = {"time": [], "signals": {}}
    with ws_sync.connect(url) as ws:
        ws.send(json.dumps({"cmd": "run", "diagram": model, "t_end": t_end, "dt": dt}))
        deadline = time.monotonic() + timeout
        while True:
            m = json.loads(ws.recv(timeout=deadline - time.monotonic()))
            if m["type"] == "progress":
                c = m["signals_chunk"]
                accum["time"] += c["time"]
                for k, chans in c["signals"].items():
                    accum["signals"].setdefault(k, [[] for _ in chans])
                    for i, ch in enumerate(chans):
                        accum["signals"][k][i] += ch
            elif m["type"] == "done":
                return accum, m["stats"]
            else:
                raise AssertionError(m.get("message"))


def test_server_matches_native_ex1_to_ex4(server):
    """같은 다이어그램 JSON → 서버 모드 결과 = 네이티브(=Pyodide) 결과, 회귀 기준값 일치."""
    for name, (build, scope_name, ch, expect) in CASES.items():
        bd, t_end, dt = build()
        model = export_json(bd)
        run(bd, t_end, dt)                            # 네이티브 기준
        sc = [b for b in bd.blocks if isinstance(b, Scope)][0]

        accum, stats = _run_via_server(server, model, t_end, dt)
        assert stats["stopped"] is False
        assert stats["steps"] == round(t_end / dt) + 1
        disp = [d for d in accum["signals"] if d.endswith(scope_name)][0]
        got = accum["signals"][disp][ch]
        assert len(got) == len(sc.data[ch]), f"{name}: 스트리밍 청크 누락"
        assert got[-1] == pytest.approx(sc.data[ch][-1], abs=1e-9), name
        assert got[-1] == pytest.approx(expect, abs=5e-7), f"{name}: 회귀 기준값"


def test_server_stop_within_1s(server):
    """장시간 실행에 stop → 1초 안에 done(stopped=True)."""
    bd, _, _ = CASES["ex1"][0]()
    model = export_json(bd)
    with ws_sync.connect(server) as ws:
        # 1M 스텝 — 순수 파이썬으로 수십 초 걸리는 크기
        ws.send(json.dumps({"cmd": "run", "diagram": model, "t_end": 1000.0, "dt": 0.001}))
        m = json.loads(ws.recv(timeout=10))           # 첫 progress = 실행 확인
        assert m["type"] == "progress"
        ws.send(json.dumps({"cmd": "stop"}))
        t0 = time.monotonic()
        while True:
            m = json.loads(ws.recv(timeout=5))
            if m["type"] == "done":
                break
        assert time.monotonic() - t0 <= 1.0, "stop 반영이 1초를 넘음"
        assert m["stats"]["stopped"] is True
        assert m["stats"]["steps"] < 1_000_000


def test_server_rejects_bad_model(server):
    """엔진 에러가 error 메시지로 돌아온다 (뷰어 상태줄 경로)."""
    model = {"blocks": [{"id": 0, "type": "Gain", "name": "g", "params": {"k": 1.0},
                         "x": 0, "y": 0}], "wires": []}   # 입력 미연결
    with ws_sync.connect(server) as ws:
        ws.send(json.dumps({"cmd": "run", "diagram": model, "t_end": 1.0, "dt": 0.01}))
        while True:
            m = json.loads(ws.recv(timeout=10))
            if m["type"] != "progress":
                break
    assert m["type"] == "error" and "연결되지 않음" in m["message"]
