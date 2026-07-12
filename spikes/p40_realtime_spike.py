"""[CLD-P40] 실시간 모드 스파이크 — 파이썬 벽시계 루프의 타이밍 타당성.

질문: 파이썬으로 50Hz 제어 루프를 돌리면 데드라인을 얼마나 지키는가?
방법: sleep-until(절대시각 기준) 스케줄러로 N 틱을 돌리며 매 틱마다
      이산 PI 제어 계산(실제 워크로드 근사)을 수행, 데드라인 오차를 기록.

판정 기준 (Bebop/터틀봇급 상위 루프):
  p95 지터 < 2ms  → 25~50Hz 속도급 명령 루프에 충분
  max  지터 > 20ms 빈발 → OS/부하 점검 필요

결과는 docs/spike_p40_realtime.md 에 기록한다.
실행: python3 spikes/p40_realtime_spike.py [rate_hz] [seconds]
"""

import math
import statistics
import sys
import time


def control_workload(t, y_meas, state):
    """실제 틱 워크로드 근사: 이산 PI + 간단한 센서 처리."""
    ref = 1.0 if t >= 1.0 else 0.0
    err = ref - y_meas
    state["i"] += 0.02 * err                      # Ki*Ts 누적
    u = 3.0 * err + state["i"]
    # 센서 필터 흉내 (수 개의 수식 — PyFunction 급 계산량)
    state["f"] = 0.9 * state["f"] + 0.1 * math.sin(t) * y_meas
    return max(-1.0, min(1.0, u))


def main(rate_hz=50.0, seconds=5.0):
    period = 1.0 / rate_hz
    n = int(seconds * rate_hz)
    state = {"i": 0.0, "f": 0.0}
    y = 0.0                                        # 가상 플랜트 (1차 지연)
    late = []                                      # 데드라인 오차 [s]

    t0 = time.monotonic()
    for k in range(n):
        deadline = t0 + k * period
        # sleep-until: 큰 구간은 sleep, 마지막 ~1ms 는 spin (지터 절감의 핵심)
        while True:
            now = time.monotonic()
            remain = deadline - now
            if remain <= 0:
                break
            time.sleep(remain - 0.001 if remain > 0.001 else 0)
        late.append(time.monotonic() - deadline)

        t = k * period
        u = control_workload(t, y, state)
        y += period * (u - y)                      # 플랜트 1스텝

    ms = [v * 1e3 for v in late]
    ms_sorted = sorted(ms)
    p = lambda q: ms_sorted[min(len(ms) - 1, int(q * len(ms)))]
    print(f"rate={rate_hz}Hz, ticks={n}, plant y({seconds}s)={y:.4f}")
    print(f"deadline 오차: p50={p(0.50):.3f}ms  p95={p(0.95):.3f}ms  "
          f"p99={p(0.99):.3f}ms  max={max(ms):.3f}ms  mean={statistics.mean(ms):.3f}ms")
    verdict = "PASS" if p(0.95) < 2.0 else "MARGINAL" if p(0.95) < 10.0 else "FAIL"
    print(f"판정(p95<2ms): {verdict}")
    return p(0.95)


if __name__ == "__main__":
    rate = float(sys.argv[1]) if len(sys.argv) > 1 else 50.0
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
    main(rate, secs)
