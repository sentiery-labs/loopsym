"""1주차 — 신호는 시간의 함수다.

아래 세 함수를 완성하라. 모두 스칼라 t 를 받아 스칼라 하나를 돌려준다.
채점:  python -m pytest test_week01.py -q
"""

import math   # sine 에서 쓴다


def step(t, t_on=1.0, height=1.0):
    """t < t_on 이면 0.0, t >= t_on 이면 height."""
    # TODO: 구현하라
    raise NotImplementedError("step 을 구현하세요")


def ramp(t, t_on=1.0, slope=1.0):
    """t < t_on 이면 0.0, 이후엔 slope * (t - t_on) 로 증가."""
    # TODO: 구현하라
    raise NotImplementedError("ramp 를 구현하세요")


def sine(t, amp=1.0, freq_hz=1.0, phase=0.0):
    """amp * sin(2π · freq_hz · t + phase)."""
    # TODO: 구현하라 (math.sin, math.pi)
    raise NotImplementedError("sine 을 구현하세요")
