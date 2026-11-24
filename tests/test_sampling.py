"""샘플 시간 의미론 — 이산(샘플) 블록의 출력은 자기 샘플 시점에만 계산되고
그 사이 구간(다음 base step 들과 RK4 minor step)에서는 그대로 유지된다 (ZOH).

Simulink 와 같은 규칙이고, 실제 디지털 제어기(PX4)가 도는 방식이다.
멀티레이트(st > dt)에서 이 규칙이 깨지면 이산 제어의 지연이 실제보다 작게
나와 결과가 낙관적이 된다.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import loopsym  # noqa: E402
from loopsym import (  # noqa: E402
    Constant, Diagram, DiscreteIntegrator, Gain, Integrator, Scope, Step, Sum,
    TransferFunction, run,
)

DT = 0.01


def _zoh_class():
    zoh = getattr(loopsym, "ZeroOrderHold", None)
    assert zoh is not None, "loopsym.ZeroOrderHold 블록이 없음"
    return zoh


def test_discrete_output_updates_only_at_its_sample_hits():
    """DiscreteIntegrator(st=0.1) 출력은 0.1 s 마다 한 번씩만 바뀐다."""
    bd = Diagram()
    c = bd.add(Constant(1.0))
    di = bd.add(DiscreteIntegrator(st=0.1))
    sc = bd.add(Scope(n_in=1))
    bd.connect(c, di)
    bd.connect(di, sc)
    run(bd, 0.35, dt=DT)

    for t, y in zip(sc.t, sc.data[0]):
        step = round(t / DT)
        expected = 0.1 * (step // 10)       # y(k) = Ts·k, 샘플 사이엔 유지
        assert abs(y - expected) < 1e-12, f"t={t:.2f}: y={y}, 기대 {expected}"


def test_zero_order_hold_samples_input_and_holds_it():
    """ZOH(st=0.1) 에 램프 t 를 넣으면 계단 0.1·floor(t/0.1) 이 나온다."""
    ZeroOrderHold = _zoh_class()
    bd = Diagram()
    one = bd.add(Constant(1.0))
    ramp = bd.add(Integrator())
    zoh = bd.add(ZeroOrderHold(st=0.1))
    sc = bd.add(Scope(n_in=1))
    bd.connect(one, ramp)
    bd.connect(ramp, zoh)
    bd.connect(zoh, sc)
    run(bd, 0.35, dt=DT)

    for t, y in zip(sc.t, sc.data[0]):
        step = round(t / DT)
        expected = 0.1 * (step // 10)
        assert abs(y - expected) < 1e-9, f"t={t:.2f}: y={y}, 기대 {expected}"


def _sampled_data_reference(kp, ki, ts, t_end, h=0.001):
    """독립 기준해: 제어기 전체를 ts 마다 계산해 ZOH 로 붙잡고, 플랜트
    1/(s+1)^2 는 잘게(h) RK4 적분한다. 반환: {base step(0.01 s) 번호: y}."""
    def f(x, u):
        return (x[1], u - 2 * x[1] - x[0])

    x, integ, u = (0.0, 0.0), 0.0, 0.0
    per, rec = round(ts / h), round(DT / h)
    out = {}
    for k in range(round(t_end / h) + 1):
        t = k * h
        if k % per == 0:
            e = (1.0 if t >= 1.0 else 0.0) - x[0]
            u = kp * e + ki * integ
            integ += ts * e
        if k % rec == 0:
            out[k // rec] = x[0]
        k1 = f(x, u)
        k2 = f((x[0] + h / 2 * k1[0], x[1] + h / 2 * k1[1]), u)
        k3 = f((x[0] + h / 2 * k2[0], x[1] + h / 2 * k2[1]), u)
        k4 = f((x[0] + h * k3[0], x[1] + h * k3[1]), u)
        x = (x[0] + h / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]),
             x[1] + h / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]))
    return out


def test_digital_pi_with_zoh_matches_sampled_data_reference():
    """오차를 ZOH 로 샘플한 PI = 실제 디지털 제어기. P 경로까지 샘플 사이에
    붙잡혀 있어야 독립 기준해와 맞는다 (minor step 에서 재계산되면 어긋남)."""
    ZeroOrderHold = _zoh_class()
    kp, ki, ts = 3.0, 2.0, 0.5
    bd = Diagram()
    ref = bd.add(Step(t_on=1.0))
    err = bd.add(Sum("+-"))
    zoh = bd.add(ZeroOrderHold(st=ts))
    gp = bd.add(Gain(kp))
    di = bd.add(DiscreteIntegrator(st=ts))
    gi = bd.add(Gain(ki))
    add = bd.add(Sum("++"))
    plant = bd.add(TransferFunction([1], [1, 2, 1]))
    sc = bd.add(Scope(n_in=1))
    bd.connect(ref, err[0]); bd.connect(plant, err[1])
    bd.connect(err, zoh); bd.connect(zoh, gp); bd.connect(zoh, di)
    bd.connect(di, gi); bd.connect(gp, add[0]); bd.connect(gi, add[1])
    bd.connect(add, plant); bd.connect(plant, sc)
    run(bd, 10.0, dt=DT)

    want = _sampled_data_reference(kp, ki, ts, 10.0)
    worst = max(abs(y - want[round(t / DT)]) for t, y in zip(sc.t, sc.data[0]))
    assert worst < 1e-6, f"기준해와 최대 차이 {worst:.3g}"
