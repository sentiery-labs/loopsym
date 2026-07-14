"""P40 재검증 — 현실적 HILS 부하 조건의 실시간 루프 지터 측정.

기존 spikes/p40_realtime_spike.py 의 결과(p95 0.001ms)는 빈 루프에 가까운
측정이었다. 여기서는 실제 HILS 조건을 전부 동시에 걸고 측정한다:

  1. 물리 부하  : 13-상태 6-DoF 쿼드로터(pos3·vel3·quat4·omega3)를 RK4 로
                  매 스텝 적분. numpy 기반 동역학을 **blocksim 블록 그래프
                  경유**(Simulator.iter_run — 직접 함수 호출이 아니라 프레임
                  워크 오버헤드 포함)로 실행.
  2. I/O 부하   : pymavlink 로 매 스텝 HIL_SENSOR 인코딩 + UDP localhost 송신.
  3. 뷰어 부하  : WebSocket 서버(스레드)로 10Hz 상태 스트리밍 + 헤드리스
                  클라이언트(서브프로세스) 연결 유지.
  4. GC        : 기본 상태 (gc.disable() 금지).
  5. 시스템     : 일반 데스크탑 부하 그대로.

사용:
  python benchmarks/p40_realtime.py                       # 50/250/500Hz × 5분
  python benchmarks/p40_realtime.py --hz 250 --duration 30
  python benchmarks/p40_realtime.py --direct              # 프레임워크 우회 비교
                                                          # (병목 분리용)

판정 (HILS 착수 기준):
  250Hz 에서 p99 스텝 간격 ≤ 4.4ms (deadline 4ms + 10%) AND 연속 miss ≤ 2

타이밍 루프 규칙:
  - 절대 데드라인 스케줄 (드리프트 누적 방지)
  - coarse sleep(목표-1ms 까지 time.sleep) + fine busy-wait 하이브리드
  - 루프 스레드를 CPU 코어 1개에 고정 시도 (권한 없으면 경고만)
  - 측정은 time.perf_counter_ns(), 기록은 사전 할당 numpy 배열
"""

import argparse
import asyncio
import datetime
import json
import math
import os
import socket
import subprocess
import sys
import threading
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blocksim import Diagram, Integrator, PyFunction, Scope, Simulator  # noqa: E402
from blocksim.realtime import hybrid_sleep, pin_to_core                 # noqa: E402  (공용 스케줄러 [P42])

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(HERE, "results")
WS_PORT = 8877          # 뷰어 스트리밍 부하용 (blocksim.server 의 8765 와 무관)
MAVLINK_ADDR = ("127.0.0.1", 14550)

# ---------------------------------------------------------------- 6-DoF 물리
G = 9.81
MASS = 1.5                      # kg
INERTIA = np.array([0.03, 0.03, 0.06])          # 대각 관성 [kg m²]
ARM = 0.25                      # 모터 팔 길이 [m]
KM = 0.02                       # 요 토크/추력 비
HOVER_F = MASS * G / 4.0        # 모터당 호버 추력 (cmd=0.5 기준의 2배 스케일)

# 마지막 스텝의 IMU 상당값 — MAVLink HIL_SENSOR 인코딩에 쓴다 (매 스텝 갱신)
_imu = {"acc": np.zeros(3), "gyro": np.zeros(3)}


def quad_dynamics(t, *u):
    """13-상태 쿼드로터 미분. u = (pos3, vel3, quat4, omega3, motor4)."""
    s = np.asarray(u[:13])
    cmd = np.asarray(u[13:17])                  # 정규화 모터 명령 [0..1]
    vel = s[3:6]
    q = s[6:10]
    w = s[10:13]

    f = cmd * 2.0 * HOVER_F                     # 모터 추력 (cmd=0.5 -> 호버)
    thrust = f.sum()
    # quad-X 배치: 1 전우+, 2 후좌-, 3 전좌+, 4 후우-  (부호는 PX4 quad-X)
    tau = np.array([
        ARM * 0.7071 * (-f[0] + f[1] + f[2] - f[3]),
        ARM * 0.7071 * (f[0] - f[1] + f[2] - f[3]),
        KM * ARM * (f[0] + f[1] - f[2] - f[3]),
    ])

    qw, qx, qy, qz = q
    # R(q): body -> NED
    R = np.array([
        [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qw * qz), 2 * (qx * qz + qw * qy)],
        [2 * (qx * qy + qw * qz), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qw * qx)],
        [2 * (qx * qz - qw * qy), 2 * (qy * qz + qw * qx), 1 - 2 * (qx * qx + qy * qy)],
    ])
    acc_body = np.array([0.0, 0.0, -thrust / MASS])       # body z 위로 추력 (NED: -z)
    acc = np.array([0.0, 0.0, G]) + R @ acc_body

    dq = 0.5 * np.array([
        -qx * w[0] - qy * w[1] - qz * w[2],
        qw * w[0] + qy * w[2] - qz * w[1],
        qw * w[1] - qx * w[2] + qz * w[0],
        qw * w[2] + qx * w[1] - qy * w[0],
    ]) + 0.5 * (1.0 - q @ q) * q                          # Baumgarte 정규화 보정

    dw = (tau - np.cross(w, INERTIA * w)) / INERTIA

    _imu["acc"], _imu["gyro"] = acc_body, w               # HIL_SENSOR 재료
    return tuple(vel) + tuple(acc) + tuple(dq) + tuple(dw)


def build_quad_diagram():
    """물리를 blocksim 블록 그래프로: 13 Integrator + 동역학 PyFunction + 모터 4."""
    bd = Diagram()
    dyn = bd.add(PyFunction(func=quad_dynamics, n_in=17, n_out=13, name="dyn"))
    integs = []
    x0 = [0.0] * 13
    x0[6] = 1.0                                           # quat = [1,0,0,0]
    for i in range(13):
        it = bd.add(Integrator(x0=x0[i], name=f"x{i}"))
        bd.connect(dyn[i], it)
        bd.connect(it, dyn[i])
        integs.append(it)
    # 모터 명령: 호버 + 미세 사인 (실제 제어기 자리 — 인코딩 비용에는 무관)
    for j in range(4):
        m = bd.add(PyFunction(f"0.5 + 0.002*sin(2*pi*0.5*t + {j * 1.57})",
                              n_in=0, name=f"motor{j}"))
        bd.connect(m, dyn[13 + j])
    sc = bd.add(Scope(n_in=2, labels=["z", "qw"], name="scope"))
    bd.connect(integs[2], sc[0])
    bd.connect(integs[6], sc[1])
    return bd


# ------------------------------------------------- 프레임워크 우회판 (병목 분리)
def run_direct_physics(n_steps, dt):
    """같은 물리를 Diagram 없이 직접 RK4 — 프레임워크 vs 물리 병목 분리용."""
    x = np.zeros(13)
    x[6] = 1.0
    cmd = (0.5, 0.5, 0.5, 0.5)
    times = np.empty(n_steps)
    for i in range(n_steps):
        t0 = time.perf_counter_ns()
        t = i * dt
        k1 = np.array(quad_dynamics(t, *x, *cmd))
        k2 = np.array(quad_dynamics(t + dt / 2, *(x + dt / 2 * k1), *cmd))
        k3 = np.array(quad_dynamics(t + dt / 2, *(x + dt / 2 * k2), *cmd))
        k4 = np.array(quad_dynamics(t + dt, *(x + dt * k3), *cmd))
        x = x + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        times[i] = (time.perf_counter_ns() - t0) / 1e6
    return times


# ---------------------------------------------------------------- 뷰어 부하
class StreamServer(threading.Thread):
    """WebSocket 서버 스레드 — 최신 상태를 10Hz 로 접속자에게 밀어낸다."""

    def __init__(self, port=WS_PORT):
        super().__init__(daemon=True)
        self.port = port
        self.state = {"t": 0.0}
        self.loop = None
        self.ready = threading.Event()

    def run(self):
        import websockets.asyncio.server as ws_server

        async def handler(ws):
            try:
                while True:
                    await ws.send(json.dumps(self.state))
                    await asyncio.sleep(0.1)              # 10Hz
            except Exception:
                pass

        async def main():
            async with ws_server.serve(handler, "127.0.0.1", self.port):
                self.ready.set()
                await asyncio.Future()

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(main())
        except Exception:
            pass


def spawn_headless_client(port=WS_PORT):
    """헤드리스 ws 클라이언트 서브프로세스 — 스트림을 실제로 소비한다."""
    code = (
        "import asyncio, websockets\n"
        "async def m():\n"
        f"    async with websockets.connect('ws://127.0.0.1:{port}') as ws:\n"
        "        while True:\n"
        "            await ws.recv()\n"
        "asyncio.run(m())\n")
    return subprocess.Popen([sys.executable, "-c", code],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------------------------------------------------------------- 측정 루프
def run_bench(hz, duration_s, server=None, mavlink=True):
    """한 주파수 측정. 반환: (스텝 간격[ms], 물리 시간[ms]) numpy 배열.

    server: 이미 떠 있는 StreamServer (전체 측정에서 1회 기동 — 스레드가
    포트를 계속 쥐고 있으므로 주파수마다 재기동하면 bind 실패한다)."""
    from pymavlink.dialects.v20 import common as mav2

    dt = 1.0 / hz
    n = int(round(duration_s * hz))

    bd = build_quad_diagram()
    sim = Simulator(bd)
    gen = sim.iter_run(t_end=duration_s + dt, dt=dt)      # n+1 스텝 이상 보장

    # MAVLink: 인코딩 비용이 핵심 — 매 스텝 pack + UDP 송신
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    mav = mav2.MAVLink(None, srcSystem=1, srcComponent=1)

    if not pin_to_core():
        print("  [경고] CPU 고정 실패 — 그대로 진행")

    intervals = np.zeros(n, dtype=np.int64)               # 스텝 간격 [ns]
    phys = np.zeros(n, dtype=np.int64)                    # 물리(그래프) 시간 [ns]
    period_ns = round(1e9 / hz)

    try:
        prev = time.perf_counter_ns()
        deadline = prev + period_ns
        for i in range(n):
            t0 = time.perf_counter_ns()
            intervals[i] = t0 - prev
            prev = t0

            step, t = next(gen)                           # ---- 물리 (블록 그래프 경유)
            phys[i] = time.perf_counter_ns() - t0

            if mavlink:                                   # ---- HIL_SENSOR 인코딩+송신
                acc, gyro = _imu["acc"], _imu["gyro"]
                msg = mav.hil_sensor_encode(
                    int(t * 1e6),
                    acc[0], acc[1], acc[2] - G,
                    gyro[0], gyro[1], gyro[2],
                    0.21, 0.0, 0.42,                      # mag
                    1013.25, 0.0, 0.0, 25.0,              # 기압/차압/고도/온도
                    0x1FFF)
                sock.sendto(msg.pack(mav), MAVLINK_ADDR)

            if server and i % max(1, hz // 10) == 0:      # ---- 10Hz 상태 갱신
                server.state = {"t": t, "step": step}

            deadline += period_ns
            hybrid_sleep(deadline)
    finally:
        sock.close()

    return intervals[1:] / 1e6, phys[1:] / 1e6            # 첫 간격(워밍업) 제외, ms


def stats(intervals_ms, phys_ms, hz):
    period_ms = 1e3 / hz
    miss = intervals_ms > 1.5 * period_ms
    # 연속 miss 최대 길이 (burst — HILS 에서 치명적)
    burst = cur = 0
    for m in miss:
        cur = cur + 1 if m else 0
        burst = max(burst, cur)
    q = lambda p: float(np.percentile(intervals_ms, p))
    return {
        "hz": hz, "steps": len(intervals_ms), "period_ms": period_ms,
        "p50": q(50), "p95": q(95), "p99": q(99), "p999": q(99.9),
        "max": float(intervals_ms.max()),
        "miss_pct": 100.0 * miss.mean(), "burst": int(burst),
        "phys_p50": float(np.percentile(phys_ms, 50)),
        "phys_p99": float(np.percentile(phys_ms, 99)),
        "phys_max": float(phys_ms.max()),
    }


def verdict_250(s):
    """판정: 250Hz p99 ≤ 4.4ms AND burst ≤ 2 → HILS 착수 가능."""
    return s["p99"] <= 4.4 and s["burst"] <= 2


def write_report(all_stats, duration_s, direct_ms=None):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    today = datetime.date.today().strftime("%Y%m%d")
    path = os.path.join(RESULTS_DIR, f"{today}_p40.md")
    L = [f"# P40 재검증 — 현실 부하 실시간 지터 ({datetime.date.today()})", ""]
    L += ["측정 조건 (전부 동시): 13-상태 6-DoF 쿼드 RK4 를 **blocksim 블록 그래프 경유**로 매 스텝 적분",
          "+ pymavlink HIL_SENSOR 인코딩/UDP 송신 매 스텝 + WebSocket 10Hz 상태 스트리밍(헤드리스 클라이언트 연결)",
          f"+ GC 기본 상태 + 일반 데스크탑 부하. 각 주파수 {duration_s:.0f}s.",
          "타이밍: 절대 데드라인 + coarse sleep/fine busy-wait 하이브리드, CPU 1코어 고정.", ""]
    L += ["| Hz | 주기 | p50 | p95 | p99 | p99.9 | max | miss율(>1.5x) | 연속miss | 물리 p50 | 물리 p99 | 물리 max |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in all_stats:
        L.append(
            f"| {s['hz']} | {s['period_ms']:.1f}ms "
            f"| {s['p50']:.3f} | {s['p95']:.3f} | {s['p99']:.3f} | {s['p999']:.3f} "
            f"| {s['max']:.3f} | {s['miss_pct']:.3f}% | {s['burst']} "
            f"| {s['phys_p50']:.3f} | {s['phys_p99']:.3f} | {s['phys_max']:.3f} |")
    L.append("")
    L.append("(단위: ms. '물리' = 블록 그래프 한 스텝(next(gen)) 소요 시간)")
    L.append("")
    s250 = next((s for s in all_stats if s["hz"] == 250), None)
    if s250:
        ok = verdict_250(s250)
        L.append(f"## 판정: 250Hz p99 {s250['p99']:.3f}ms (기준 ≤ 4.4ms), "
                 f"연속 miss {s250['burst']} (기준 ≤ 2) → "
                 f"**{'PASS — HILS/P42 착수 가능' if ok else 'FAIL — 병목 분리 필요 (프롬프트 4)'}**")
    if direct_ms is not None:
        L += ["", f"프레임워크 우회(직접 RK4) 물리 p50: {np.percentile(direct_ms, 50):.3f}ms "
                  f"/ p99: {np.percentile(direct_ms, 99):.3f}ms — 그래프 경유와의 차이가 프레임워크 오버헤드."]
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--hz", type=int, nargs="+", default=[50, 250, 500])
    ap.add_argument("--duration", type=float, default=300.0, help="주파수당 측정 시간 [s]")
    ap.add_argument("--no-stream", action="store_true", help="뷰어 부하 끄기 (비교용)")
    ap.add_argument("--no-mavlink", action="store_true", help="I/O 부하 끄기 (비교용)")
    ap.add_argument("--direct", action="store_true",
                    help="프레임워크 우회 직접 RK4 물리 시간만 측정 (병목 분리)")
    args = ap.parse_args()

    if args.direct:
        d = run_direct_physics(5000, 1.0 / 250)
        print(f"직접 RK4 물리: p50 {np.percentile(d, 50):.3f}ms  "
              f"p99 {np.percentile(d, 99):.3f}ms  max {d.max():.3f}ms")
        return

    server = client = None
    if not args.no_stream:                                # 뷰어 부하는 전체 측정에서 1회 기동
        server = StreamServer()
        server.start()
        if not server.ready.wait(5):
            raise RuntimeError("스트리밍 서버 기동 실패")
        client = spawn_headless_client()
        time.sleep(0.5)                                   # 클라이언트 접속 대기

    all_stats = []
    for hz in args.hz:
        print(f"[{hz}Hz × {args.duration:.0f}s = {int(hz * args.duration):,} steps] 측정 중…")
        iv, ph = run_bench(hz, args.duration,
                           server=server, mavlink=not args.no_mavlink)
        s = stats(iv, ph, hz)
        all_stats.append(s)
        print(f"  p50 {s['p50']:.3f}  p95 {s['p95']:.3f}  p99 {s['p99']:.3f}  "
              f"p99.9 {s['p999']:.3f}  max {s['max']:.3f} ms | "
              f"miss {s['miss_pct']:.3f}%  burst {s['burst']} | "
              f"물리 p50 {s['phys_p50']:.3f} p99 {s['phys_p99']:.3f} ms")

    if client:
        client.terminate()
    direct = run_direct_physics(2000, 1.0 / 250)
    path = write_report(all_stats, args.duration, direct)
    print("리포트:", path)
    s250 = next((s for s in all_stats if s["hz"] == 250), None)
    if s250:
        print("판정(250Hz):", "PASS" if verdict_250(s250) else "FAIL")


if __name__ == "__main__":
    main()
