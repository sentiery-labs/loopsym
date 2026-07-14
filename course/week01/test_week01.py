"""1주차 채점기 — 정식 blocksim 블록을 정답 오라클로 사용."""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", ".."))     # blocksim (정답 오라클)

import signals                                          # noqa: E402  (학생 코드)
from blocksim import Sine, Step                         # noqa: E402

TS = [0.0, 0.5, 0.999, 1.0, 1.001, 1.5, 3.7, 10.0]


def test_step_matches_oracle():
    oracle = Step(t_on=1.0, height=2.5)
    for t in TS:
        assert signals.step(t, 1.0, 2.5) == oracle.output(t, None, ())[0], f"t={t}"


def test_step_default_args():
    assert signals.step(0.5) == 0.0 and signals.step(2.0) == 1.0


def test_ramp():
    for t in TS:
        expect = 0.0 if t < 1.0 else 0.7 * (t - 1.0)
        assert abs(signals.ramp(t, 1.0, 0.7) - expect) < 1e-12, f"t={t}"


def test_sine_matches_oracle():
    oracle = Sine(amp=2.0, freq_hz=0.5, phase=0.3)
    for t in TS:
        assert abs(signals.sine(t, 2.0, 0.5, 0.3)
                   - oracle.output(t, None, ())[0]) < 1e-12, f"t={t}"


def test_sine_is_pure():
    """같은 t 면 항상 같은 값 (전역 상태 금지)."""
    assert signals.sine(0.37) == signals.sine(0.37)
    assert abs(signals.sine(0.0, amp=3.0, phase=math.pi / 2) - 3.0) < 1e-12
