"""loopsym.realtime — 실시간(벽시계) 실행 모드. [CLD-P42]

배치 시뮬레이션(sim 모드)은 최대한 빨리 도는 반면, 실시간 모드는
시뮬레이션 시간을 벽시계에 1:1 (speed 배속) 로 맞춰 진행한다.
실기체(Bebop/ROS2/MAVLink 블록)와 HILS 는 이 모드 위에서 돈다.

P40 재검증(benchmarks/results/20260714_p40.md)에서 확립한 원칙:
  1. 절대 데드라인 스케줄 — 스텝마다 "지금+주기"가 아니라 데드라인을
     주기씩 전진시켜 드리프트가 누적되지 않는다.
  2. coarse sleep + fine busy-wait — time.sleep 의 해상도 한계(~1ms)를
     마지막 1ms 스핀으로 회피. 이 조합으로 250Hz p99 4.002ms 실측.
  3. physics never waits — on_step 콜백(스트리밍, 로깅)은 절대 블로킹
     금지. I/O 는 별도 스레드 + non-blocking queue 로 뺄 것 (서버 모드의
     구조가 그 본보기).

순수 표준 라이브러리 — 코어 무의존성 원칙(교육용) 유지.
"""

import os
import time

from .core import Diagram
from .sim import Simulator


def pin_to_core():
    """호출 스레드를 CPU 코어 1개에 고정 시도. 실패하면 False (경고만)."""
    try:
        os.sched_setaffinity(0, {sorted(os.sched_getaffinity(0))[-1]})
        return True
    except (AttributeError, PermissionError, OSError):
        return False


def hybrid_sleep(deadline_ns):
    """deadline(perf_counter_ns 기준)까지 대기 — coarse sleep + 마지막 ~1ms 스핀."""
    while True:
        remain = deadline_ns - time.perf_counter_ns()
        if remain <= 0:
            return
        if remain > 1_200_000:
            time.sleep((remain - 1_000_000) / 1e9)
        # 마지막 ~1ms 는 busy-wait


class Pacer:
    """절대 데드라인 페이서. 매 스텝 wait() 하면 벽시계에 맞춰 진행된다."""

    def __init__(self, dt, speed=1.0):
        self.period_ns = round(dt * 1e9 / speed)
        self.deadline = None

    def wait(self):
        if self.deadline is None:
            self.deadline = time.perf_counter_ns()
        self.deadline += self.period_ns
        hybrid_sleep(self.deadline)


class JitterMeter:
    """스텝 간격 지터 기록계. tick() 을 루프 선두에서 부른다."""

    def __init__(self, dt, speed=1.0):
        self.period_ms = dt * 1e3 / speed
        self.prev = None
        self.intervals = []          # [ms]

    def tick(self):
        now = time.perf_counter_ns()
        if self.prev is not None:
            self.intervals.append((now - self.prev) / 1e6)
        self.prev = now

    def stats(self):
        iv = sorted(self.intervals)
        if not iv:
            return {}
        pct = lambda p: iv[min(len(iv) - 1, int(p / 100 * len(iv)))]
        limit = 1.5 * self.period_ms
        burst = cur = miss = 0
        for v in self.intervals:
            if v > limit:
                miss += 1
                cur += 1
                burst = max(burst, cur)
            else:
                cur = 0
        return {
            "period_ms": self.period_ms, "steps": len(iv),
            "p50": pct(50), "p95": pct(95), "p99": pct(99), "max": iv[-1],
            "miss_pct": 100.0 * miss / len(iv), "burst": burst,
        }


def run_realtime(diagram, t_end, dt=0.01, speed=1.0,
                 on_step=None, stop_event=None, pin=True):
    """다이어그램을 벽시계 속도로 실행한다 (배치 run() 의 실시간 판).

    수치 결과는 run(bd, t_end, dt) 과 완전히 같다 — 페이싱은 스텝 사이에
    끼는 대기일 뿐 적분에는 관여하지 않는다.

    diagram    : Diagram 또는 이미 만든 Simulator
    speed      : 1.0 = 실시간, 2.0 = 2배속, 0.5 = 절반 속도
    on_step    : callable(step, t) — 매 스텝 뒤 호출. **non-blocking 필수.**
    stop_event : threading.Event — set 되면 다음 스텝 경계에서 중단
    pin        : CPU 1코어 고정 시도 (권한 없으면 조용히 진행)

    반환: 지터 통계 dict (JitterMeter.stats() + stopped/pinned/elapsed_s)
    """
    sim = diagram if isinstance(diagram, Simulator) else Simulator(diagram)
    pinned = pin_to_core() if pin else False
    pacer = Pacer(dt, speed)
    meter = JitterMeter(dt, speed)
    stopped = False
    t0 = time.perf_counter()
    for step, t in sim.iter_run(t_end, dt):
        meter.tick()
        if stop_event is not None and stop_event.is_set():
            stopped = True
            break
        if on_step is not None:
            on_step(step, t)
        pacer.wait()
    stats = meter.stats()
    stats.update(stopped=stopped, pinned=pinned,
                 elapsed_s=time.perf_counter() - t0)
    return stats
