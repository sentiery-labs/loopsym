"""7주차 채점기 — ★브리지★: 내 엔진의 결과 = 정식 blocksim = 회귀 기준값.

기준값 (정식판 예제 회귀값, 6자리): ex1 y(10s)=1.000189, ex2 θ(8s)=0.306499.
"""

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", ".."))

import mybs                                             # noqa: E402  (제공 엔진)
import mymodel                                          # noqa: E402  (학생 모델)
import blocksim as bs                                   # noqa: E402  (정답 오라클)

EX1_Y10 = 1.000189
EX2_TH8 = 0.306499


def _oracle_ex1():
    bd = bs.Diagram()
    ref = bd.add(bs.Step(t_on=1.0)); err = bd.add(bs.Sum("+-"))
    kp = bd.add(bs.Gain(3.0)); integ = bd.add(bs.Integrator()); ki = bd.add(bs.Gain(2.0))
    pi = bd.add(bs.Sum("++")); plant = bd.add(bs.TransferFunction([1], [1, 2, 1]))
    sc = bd.add(bs.Scope(n_in=1))
    bd.connect(ref, err[0]); bd.connect(plant, err[1])
    bd.connect(err, kp); bd.connect(err, integ); bd.connect(integ, ki)
    bd.connect(kp, pi[0]); bd.connect(ki, pi[1]); bd.connect(pi, plant)
    bd.connect(plant, sc)
    bs.run(bd, 10.0, 0.01)
    return sc.data[0]


def test_pi_loop_matches_reference():
    bd, sc = mymodel.build_pi_loop()
    mybs.simulate(bd, 10.0, 0.01)
    assert sc.data[0][-1] == pytest.approx(EX1_Y10, abs=5e-7), \
        "회귀 기준값(1.000189)과 6자리 불일치 — 배선/게인을 확인"


def test_pi_loop_matches_blocksim_pointwise():
    """전 구간이 정식 blocksim(전달함수 플랜트판)과 1e-9 이내 — 브리지 완성."""
    bd, sc = mymodel.build_pi_loop()
    mybs.simulate(bd, 10.0, 0.01)
    oracle = _oracle_ex1()
    assert len(sc.data[0]) == len(oracle)
    err = max(abs(a - b) for a, b in zip(sc.data[0], oracle))
    assert err < 1e-9, f"blocksim 과 최대차 {err}"


def test_pi_loop_step_timing():
    """t_on=1.0 전에는 아무 일도 없어야 한다 (setpoint 확인)."""
    bd, sc = mymodel.build_pi_loop()
    mybs.simulate(bd, 10.0, 0.01)
    assert max(abs(v) for v in sc.data[0][:100]) < 1e-12


def test_pendulum_matches_reference():
    bd, sc = mymodel.build_pendulum()
    mybs.simulate(bd, 8.0, 0.005)
    assert sc.data[0][-1] == pytest.approx(EX2_TH8, abs=5e-7), \
        "θ(8s)=0.306499 와 불일치 — 동역학/제어기 식을 확인"


def test_pendulum_shows_steady_state_error():
    """PD 만으로는 0.8 에 못 간다 — '왜 I 가 필요한가'의 증거를 확인."""
    bd, sc = mymodel.build_pendulum()
    mybs.simulate(bd, 8.0, 0.005)
    assert sc.data[0][-1] < 0.5
