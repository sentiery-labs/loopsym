"""로컬 서버 모드(loopsym/server.py) 통합 테스트.

실제로 `python -m loopsym.server` 서브프로세스를 띄우고 websockets
클라이언트(뷰어의 서버 모드와 같은 프로토콜)로:
  1. ex1~ex4 회귀 — 결과가 네이티브 엔진(= Pyodide 모드와 동일 코드)과 일치
  2. 시뮬레이션 중 stop 이 1초 안에 반영
  3. 접속 키·출처 검사 — 키 없는 접속과 다른 웹사이트 출처는 거부
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

from loopsym import Scope, export_json, render_html, run   # noqa: E402
from loopsym.auth import server_key                   # noqa: E402
from tests.test_pyodide_smoke import CASES            # noqa: E402  (ex1~ex4 모델 공유)

ws_exc = pytest.importorskip("websockets.exceptions")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REJECTED = 4403        # 서버가 키/출처 검사에서 끊을 때 쓰는 close code


@pytest.fixture(scope="module")
def server():
    """뷰어처럼 접속 키를 붙인 URL 을 돌려준다."""
    with socket.socket() as s:                 # 빈 포트 확보
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [sys.executable, "-m", "loopsym.server", "--port", str(port)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    url = f"ws://127.0.0.1:{port}/ws?key={server_key()}"
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


# ---------------------------------------------------------------- 접속 키·출처
def _close_code(url, origin=None):
    """접속해서 run 을 보내 본다. 서버가 끊으면 close code, 아니면 None."""
    bd, t_end, dt = CASES["ex1"][0]()
    try:
        with ws_sync.connect(url, origin=origin, open_timeout=5) as ws:
            ws.send(json.dumps({"cmd": "run", "diagram": export_json(bd),
                                "t_end": 0.1, "dt": dt}))
            while True:
                m = json.loads(ws.recv(timeout=10))
                if m["type"] in ("done", "error"):
                    return None
    except ws_exc.ConnectionClosed as e:
        return e.rcvd.code if e.rcvd else None


def test_server_rejects_connection_without_key(server):
    """키 없는 접속(다른 웹사이트가 ws://localhost 로 붙는 경우)은 끊는다."""
    base = server.split("?")[0]
    assert _close_code(base) == REJECTED
    assert _close_code(base + "?key=wrong") == REJECTED


def test_server_rejects_foreign_origin_even_with_key(server):
    """키가 새어 나가도 다른 웹사이트 출처에서는 실행하지 않는다."""
    assert _close_code(server, origin="https://evil.example") == REJECTED


def test_server_accepts_viewer_with_key(server):
    """키를 가진 file:// 뷰어(Origin null)와 localhost 페이지는 그대로 동작한다."""
    assert _close_code(server, origin="null") is None
    assert _close_code(server, origin="http://localhost:8000") is None


def test_render_html_embeds_server_key(tmp_path):
    """render_html 로 만든 뷰어에 서버 접속 키가 심어진다."""
    bd, _, _ = CASES["ex1"][0]()
    html = open(render_html(bd, str(tmp_path / "v.html")), encoding="utf-8").read()
    assert server_key() in html


def test_render_html_keeps_embedded_engine_sources_intact(tmp_path):
    """키 치환이 뷰어에 심은 엔진 소스(viz.py 안의 표식 문자열)까지 건드리면
    JS 가 깨진다 — 심은 소스가 원본 파일과 글자 그대로 같아야 한다."""
    import re
    import loopsym.viz as viz
    bd, _, _ = CASES["ex1"][0]()
    html = open(render_html(bd, str(tmp_path / "v.html")), encoding="utf-8").read()
    m = re.search(r"const BLOCKSIM_SRC = (\{.*?\});\n", html, re.S)
    assert m, "BLOCKSIM_SRC 를 찾지 못함"
    try:
        src = json.loads(m.group(1))
    except ValueError as e:
        pytest.fail(f"심은 엔진 소스 JSON 이 깨짐: {e}")
    with open(viz.__file__, encoding="utf-8") as f:
        assert src["viz.py"] == f.read()
