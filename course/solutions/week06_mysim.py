"""6주차 정답 — mysim.py 대체용."""

from myblocks import Scope


def _make_state(bd):
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
    inputs = _eval_outputs(bd, order, offsets, t, x)
    dx = [0.0] * len(x)
    for b in bd.blocks:
        if b.state_size:
            xs = tuple(x[offsets[b]:offsets[b] + b.state_size])
            for i, v in enumerate(b.derivative(t, inputs[b], xs)):
                dx[offsets[b] + i] = v
    return dx


def simulate(bd, t_end, dt=0.01, method="rk4"):
    order = bd.compile()
    offsets, x = _make_state(bd)
    n = round(t_end / dt)
    for step in range(n + 1):
        t = step * dt
        inputs = _eval_outputs(bd, order, offsets, t, x)
        for b in bd.blocks:
            if isinstance(b, Scope):
                b.record(t, inputs[b])
        f = lambda tt, xx: _deriv(bd, order, offsets, tt, xx)
        if method == "euler":
            k1 = f(t, x)
            x = [xi + dt * d for xi, d in zip(x, k1)]
        else:
            k1 = f(t, x)
            k2 = f(t + dt / 2, [xi + dt / 2 * k for xi, k in zip(x, k1)])
            k3 = f(t + dt / 2, [xi + dt / 2 * k for xi, k in zip(x, k2)])
            k4 = f(t + dt, [xi + dt * k for xi, k in zip(x, k3)])
            x = [xi + dt / 6 * (a + 2 * b_ + 2 * c + d)
                 for xi, a, b_, c, d in zip(x, k1, k2, k3, k4)]
    return bd
