"""6주차 — 시간을 흐르게 하라: 오일러에서 RK4 로.

미분방정식 dx/dt = f(t, x) 를 코드로 푸는 것이 솔버의 전부다.
2단계 출력 평가(_eval_outputs)와 상태 관리는 제공한다 — 적분 공식만
네 손으로 써 넣어라. myblocks.py 의 Integrator 도 이번 주 TODO.

채점:  python -m pytest test_week06.py -q
"""

from myblocks import Scope


def _make_state(bd):
    """[제공] 모든 블록의 상태를 하나의 리스트 x 로 이어붙인다."""
    offsets, ofs = {}, 0
    for b in bd.blocks:
        offsets[b] = ofs
        ofs += b.state_size
    x = [0.0] * ofs
    for b in bd.blocks:
        for i, v in enumerate(b.initial()):
            x[offsets[b] + i] = v
    return offsets, x


def _eval_outputs(bd, order, offsets, t, x):
    """[제공] 2단계 평가: ①상태 블록(입력 불필요 — 고리가 끊기는 이유!)
    ②feedthrough 블록(위상 순서). 반환: {블록: 입력 튜플}."""
    bstate = lambda b: tuple(x[offsets[b]:offsets[b] + b.state_size])
    signals = {}
    for b in bd.blocks:
        if not b.feedthrough:
            for i, v in enumerate(b.output(t, None, bstate(b))):
                signals[(b, i)] = v
    for b in order:
        if b.feedthrough:
            u = tuple(signals[bd.wires[(b, i)]] for i in range(b.n_in))
            for i, v in enumerate(b.output(t, u, bstate(b))):
                signals[(b, i)] = v
    return {b: tuple(signals[bd.wires[(b, i)]] for i in range(b.n_in))
            for b in bd.blocks}


def _deriv(bd, order, offsets, t, x):
    """[제공] 상태 미분 벡터 dx = f(t, x)."""
    inputs = _eval_outputs(bd, order, offsets, t, x)
    dx = [0.0] * len(x)
    for b in bd.blocks:
        if b.state_size:
            xs = tuple(x[offsets[b]:offsets[b] + b.state_size])
            for i, v in enumerate(b.derivative(t, inputs[b], xs)):
                dx[offsets[b] + i] = v
    return dx


def simulate(bd, t_end, dt=0.01, method="rk4"):
    """0 부터 t_end 까지 고정 스텝. method: 'euler' 또는 'rk4'."""
    order = bd.compile()
    offsets, x = _make_state(bd)
    n = round(t_end / dt)
    for step in range(n + 1):
        t = step * dt                     # 누적 덧셈 대신 곱셈 (드리프트 방지)
        inputs = _eval_outputs(bd, order, offsets, t, x)
        for b in bd.blocks:
            if isinstance(b, Scope):
                b.record(t, inputs[b])

        f = lambda tt, xx: _deriv(bd, order, offsets, tt, xx)
        if method == "euler":
            # TODO 1 (오일러): x_{k+1} = x_k + dt * f(t, x_k)
            #   힌트: k1 = f(t, x)  →  새 x 를 리스트 컴프리헨션으로.
            raise NotImplementedError
        else:
            # TODO 2 (RK4): 기울기 4개의 가중 평균.
            #   k1 = f(t, x)
            #   k2 = f(t + dt/2, x + dt/2·k1)
            #   k3 = f(t + dt/2, x + dt/2·k2)
            #   k4 = f(t + dt,   x + dt·k3)
            #   x  = x + dt/6 · (k1 + 2k2 + 2k3 + k4)
            #   (벡터 연산은 zip + 컴프리헨션으로 — numpy 없이!)
            raise NotImplementedError
    return bd
