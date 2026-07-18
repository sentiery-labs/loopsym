"""loopsym.server — 로컬 파이썬 서버 실행 모드 (FastAPI + WebSocket).

    python -m loopsym.server            # ws://localhost:8765
    python -m loopsym.server --port N

뷰어는 페이지 로드 때 이 주소로 접속을 시도해서, 성공하면 "Local Server"
모드(시뮬레이션이 이 프로세스에서 돌고 결과가 스트리밍됨), 실패하면
Pyodide 모드로 자동 폴백한다. HILS(실제 Pixhawk)와 실시간 러너(P42)는
브라우저 샌드박스 밖이 필요하므로 이 모드에서만 동작한다.

프로토콜 (WebSocket, JSON):
  client→server: {"cmd": "run", "diagram": {...}, "t_end": 10, "dt": 0.004,
                  "mode": "sim" | "realtime"}          # 기본 "sim"
  client→server: {"cmd": "stop"}
  client→server: {"cmd": "joy", "axes": [...], "buttons": [0/1,...]}
                  # 게임패드 라이브 입력 — 실행 중 Joystick 블록으로 라우팅
  server→client: {"type": "progress", "t": 3.2,
                  "signals_chunk": {"time": [...], "signals": {...}, "labels": {...}}}
  server→client: {"type": "done", "stats": {"steps": N, "elapsed_s": s, "stopped": bool,
                  "mode": "...", "timing": {...}}}     # timing 은 realtime 모드만 (지터 통계)
  server→client: {"type": "error", "message": "..."}

실행 모드 [CLD-P42]:
  sim      — 최대 속도 배치 실행 (결과가 목적)
  realtime — 벽시계 1:1 페이싱 (loopsym.realtime 스케줄러; 뷰어 Scope 가
             라이브로 흐른다 = external mode. HILS/실기체 블록의 기반)

스레딩 구조 (중요 — 실시간 모드의 기반):
  **physics never waits for the viewer.**
  시뮬레이션 루프는 전용 스레드에서 돌고, 결과 청크는 non-blocking
  queue(put_nowait)로만 내보낸다. 큐가 가득 차면 가장 오래된 청크를
  버린다 — 시각화(WebSocket 전송)가 물리 루프를 절대 막지 않는다.
  배치 실행도 같은 스트리밍 경로를 쓰므로, 나중에 실시간 모드가 와도
  전송 계층은 그대로다.
"""

import argparse
import asyncio
import json
import queue
import threading
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .realtime import JitterMeter, Pacer
from .sim import Simulator
from .viz import load_json
from .webapi import MAX_STEPS, _scope_paths

CHUNK_WALL_S = 0.1      # 청크 전송 주기 (wall clock) ≈ 10Hz
QUEUE_SIZE = 64         # 넘치면 오래된 청크부터 버린다

app = FastAPI(title="loopsym local server")


def _put_drop_oldest(q, item):
    """put_nowait — 가득 차면 가장 오래된 것을 버리고 넣는다 (물리는 안 기다림)."""
    while True:
        try:
            q.put_nowait(item)
            return
        except queue.Full:
            try:
                q.get_nowait()
            except queue.Empty:
                pass


def _sim_worker(model, t_end, dt, mode, out_q, stop_evt, joy_state=None):
    """전용 스레드: 시뮬레이션을 돌리며 Scope 증분을 청크로 내보낸다."""
    try:
        if not (t_end > 0 and dt > 0):
            raise ValueError("t_end, dt 는 양수여야 합니다.")
        if t_end / dt > MAX_STEPS:
            raise ValueError(f"스텝 수가 너무 큽니다 (t_end/dt ≤ {MAX_STEPS:,}).")
        if mode not in ("sim", "realtime"):
            raise ValueError(f"알 수 없는 mode: {mode!r} ('sim' 또는 'realtime')")
        bd = load_json(model)
        scopes = _scope_paths(bd)
        labels = {disp: list(s.labels) for disp, s in scopes}
        sim = Simulator(bd)

        # 게임패드 라이브 입력 → Joystick 블록 연결 (ws 핸들러가 dict 를 갱신)
        if joy_state is not None:
            from .joystick import Joystick
            for b in sim.bd.blocks:
                if isinstance(b, Joystick):
                    b.attach(joy_state)

        sent = 0                       # 이미 보낸 샘플 수 (Scope 는 전부 같은 major step 에 기록)
        t0 = time.monotonic()
        last_flush = t0
        stopped = False
        t_now = 0.0

        def flush():
            nonlocal sent
            if scopes:
                n = len(scopes[0][1].t)
                if n == sent:
                    return
                chunk = {
                    "time": scopes[0][1].t[sent:n],
                    "signals": {disp: [ch[sent:n] for ch in s.data] for disp, s in scopes},
                    "labels": labels,
                }
                sent = n
            else:
                chunk = {"time": [], "signals": {}, "labels": {}}
            _put_drop_oldest(out_q, {"type": "progress", "t": t_now, "signals_chunk": chunk})

        # realtime 모드: 벽시계 페이싱 + 지터 계측 (sim 모드는 최대 속도)
        pacer = Pacer(dt) if mode == "realtime" else None
        meter = JitterMeter(dt) if mode == "realtime" else None

        steps = 0
        for step, t in sim.iter_run(t_end, dt):
            if meter:
                meter.tick()
            steps, t_now = step + 1, t
            if stop_evt.is_set():
                stopped = True
                break
            now = time.monotonic()
            if now - last_flush >= CHUNK_WALL_S:
                flush()
                last_flush = now
            if pacer:
                pacer.wait()          # 스텝 경계에서만 대기 — 적분에는 무관
        flush()   # 남은 증분
        stats = {"steps": steps, "elapsed_s": time.monotonic() - t0,
                 "stopped": stopped, "mode": mode}
        if meter:
            stats["timing"] = meter.stats()
        # done/error 는 유실되면 안 되므로 블로킹 put (물리는 이미 끝났다)
        out_q.put({"type": "done", "stats": stats})
    except Exception as e:
        out_q.put({"type": "error", "message": str(e)})


async def _pump(ws, out_q):
    """큐 → WebSocket. done/error 를 보낸 뒤 끝난다."""
    while True:
        try:
            item = out_q.get_nowait()
        except queue.Empty:
            await asyncio.sleep(0.02)
            continue
        await ws.send_text(json.dumps(item))
        if item["type"] in ("done", "error"):
            return


async def _handle(ws):
    await ws.accept()
    stop_evt = None
    pump_task = None
    joy_state = None
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            cmd = msg.get("cmd")
            if cmd == "run":
                if pump_task and not pump_task.done():
                    await ws.send_text(json.dumps(
                        {"type": "error", "message": "이미 실행 중입니다 — stop 먼저."}))
                    continue
                out_q = queue.Queue(maxsize=QUEUE_SIZE)
                stop_evt = threading.Event()
                joy_state = {}
                threading.Thread(
                    target=_sim_worker,
                    args=(msg["diagram"], float(msg["t_end"]), float(msg["dt"]),
                          msg.get("mode", "sim"), out_q, stop_evt, joy_state),
                    daemon=True).start()
                pump_task = asyncio.ensure_future(_pump(ws, out_q))
            elif cmd == "joy":
                if joy_state is not None:      # 갱신만 — 물리 루프는 안 기다린다
                    joy_state["axes"] = msg.get("axes") or []
                    joy_state["buttons"] = msg.get("buttons") or []
            elif cmd == "stop":
                if stop_evt:
                    stop_evt.set()
            else:
                await ws.send_text(json.dumps(
                    {"type": "error", "message": f"알 수 없는 cmd: {cmd!r}"}))
    except WebSocketDisconnect:
        pass
    finally:
        if stop_evt:
            stop_evt.set()          # 클라이언트가 사라지면 물리도 정지
        if pump_task:
            pump_task.cancel()


# 뷰어는 ws://localhost:8765/ws 로 붙는다. "/" 도 같이 열어 둔다.
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await _handle(ws)


@app.websocket("/")
async def ws_root(ws: WebSocket):
    await _handle(ws)


def main():
    import uvicorn
    ap = argparse.ArgumentParser(description="loopsym 로컬 서버 (뷰어가 자동 감지)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    print(f"loopsym server — ws://{args.host}:{args.port}/ws (뷰어를 새로고침하면 잡습니다)")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
