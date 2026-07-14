"""1주차 정답 — signals.py 대체용."""

import math


def step(t, t_on=1.0, height=1.0):
    """t < t_on 이면 0.0, t >= t_on 이면 height."""
    return height if t >= t_on else 0.0


def ramp(t, t_on=1.0, slope=1.0):
    """t < t_on 이면 0.0, 이후엔 slope * (t - t_on) 로 증가."""
    return slope * (t - t_on) if t >= t_on else 0.0


def sine(t, amp=1.0, freq_hz=1.0, phase=0.0):
    """amp * sin(2π · freq_hz · t + phase)."""
    return amp * math.sin(2 * math.pi * freq_hz * t + phase)
