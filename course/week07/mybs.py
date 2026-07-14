"""mybs — 1~6주차에 우리 손으로 만든 미니 loopsym (7주차 제공 완성본).

정식 loopsym 의 축소판: 스칼라 신호, 연속 블록, 고정 스텝 오일러/RK4.
(서브시스템·이산 블록·마스크는 정식판에만 있다 — 심화 과제 참조.)

의미론은 정식판과 동일하게 맞췄다:
  1) feedthrough=False 블록(적분기)의 출력을 먼저 계산 — 피드백 고리가 끊긴다
  2) feedthrough 블록은 위상 정렬 순서로
  3) 상태 미분을 모아 오일러/RK4 한 스텝
그래서 같은 다이어그램이면 정식 loopsym 과 같은 숫자가 나온다 (7주차 브리지).
"""

import math

# PyFunction 식에서 쓸 수 있는 안전한 이름들
_MATH_ENV = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
for _f in (abs, min, max):
    _MATH_ENV[_f.__name__] = _f


# ======================================================================
# 2~3주차 — 블록
# ======================================================================
class Block:
    """모든 블록의 부모. 자식이 정하는 것: n_in/n_out/state_size/feedthrough."""

    n_in = 0
    n_out = 1
    state_size = 0
    feedthrough = True          # 출력이 '지금 입력'에 즉시 의존하는가

    def __init__(self, name=None):
        self.name = name or type(self).__name__

    def __getitem__(self, i):
        """block[i] -> (block, i) 포트 튜플. connect 에서 쓴다."""
        return (self, i)

    def output(self, t, u, x):
        return ()

    def derivative(self, t, u, x):
        return ()

    def initial(self):
        return (0.0,) * self.state_size


class Constant(Block):
    n_in = 0

    def __init__(self, value=1.0, name=None):
        super().__init__(name)
        self.value = value

    def output(self, t, u, x):
        return (self.value,)


class Step(Block):
    """t_on 이전엔 0, 이후엔 height."""

    n_in = 0

    def __init__(self, t_on=1.0, height=1.0, name=None):
        super().__init__(name)
        self.t_on, self.height = t_on, height

    def output(self, t, u, x):
        return (self.height if t >= self.t_on else 0.0,)


class Gain(Block):
    n_in = 1

    def __init__(self, k=1.0, name=None):
        super().__init__(name)
        self.k = k

    def output(self, t, u, x):
        return (self.k * u[0],)


class Saturation(Block):
    n_in = 1

    def __init__(self, lo=-1.0, hi=1.0, name=None):
        super().__init__(name)
        self.lo, self.hi = lo, hi

    def output(self, t, u, x):
        return (min(max(u[0], self.lo), self.hi),)


class Offset(Block):
    """y = u + c  (2주차 과제 블록 — 정식판엔 없다)."""

    n_in = 1

    def __init__(self, c=0.0, name=None):
        super().__init__(name)
        self.c = c

    def output(self, t, u, x):
        return (u[0] + self.c,)


class Sum(Block):
    """signs='+-' 부호 문자열이 입력 수와 부호를 정한다."""

    def __init__(self, signs="++", name=None):
        super().__init__(name)
        if not signs or not all(s in "+-" for s in signs):
            raise ValueError("signs 는 '+' 와 '-' 로만 구성")
        self.signs = signs
        self.n_in = len(signs)

    def output(self, t, u, x):
        return (sum(v if s == "+" else -v for s, v in zip(self.signs, u)),)


class Product(Block):
    """ops='*/' 이면 y = u0 / u1."""

    def __init__(self, ops="**", name=None):
        super().__init__(name)
        if not ops or not all(c in "*/" for c in ops):
            raise ValueError("ops 는 '*' 와 '/' 로만 구성")
        self.ops = ops
        self.n_in = len(ops)

    def output(self, t, u, x):
        y = 1.0
        for c, v in zip(self.ops, u):
            y = y * v if c == "*" else y / v
        return (y,)


class PyFunction(Block):
    """식 문자열 블록: 입력은 u0, u1, ... 시간은 t, math 함수 사용 가능."""

    def __init__(self, expr, n_in=1, n_out=1, name=None):
        super().__init__(name)
        self.expr = expr
        self.n_in, self.n_out = n_in, n_out
        self._code = compile(expr, f"<PyFunction {self.name}>", "eval")

    def output(self, t, u, x):
        env = dict(_MATH_ENV, t=t, **{f"u{i}": v for i, v in enumerate(u)})
        y = eval(self._code, {"__builtins__": {}}, env)
        return y if isinstance(y, tuple) else (y,)


# ======================================================================
# 6주차 — 상태 블록 (피드백 고리를 끊는 주인공)
# ======================================================================
class Integrator(Block):
    """y = x,  dx/dt = u.  출력이 상태만으로 정해지므로 feedthrough=False."""

    n_in = 1
    state_size = 1
    feedthrough = False

    def __init__(self, x0=0.0, name=None):
        super().__init__(name)
        self.x0 = x0

    def initial(self):
        return (self.x0,)

    def output(self, t, u, x):
        return (x[0],)

    def derivative(self, t, u, x):
        return (u[0],)


class Scope(Block):
    """신호 기록계 — 매 major step 에 입력을 저장."""

    n_out = 0
    feedthrough = True

    def __init__(self, n_in=1, labels=None, name=None):
        super().__init__(name)
        self.n_in = n_in
        self.labels = labels or [f"in{i}" for i in range(n_in)]
        self.t = []
        self.data = [[] for _ in range(n_in)]

    def output(self, t, u, x):
        return ()

    def record(self, t, u):
        self.t.append(t)
        for i, v in enumerate(u):
            self.data[i].append(v)


# ======================================================================
# 4~5주차 — 다이어그램과 실행 순서
# ======================================================================
class AlgebraicLoopError(Exception):
    """feedthrough 블록끼리 고리를 이루면 계산 순서를 정할 수 없다."""


class Diagram:
    def __init__(self):
        self.blocks = []
        self.wires = {}          # (dst_block, dst_idx) -> (src_block, src_idx)

    def add(self, block):
        self.blocks.append(block)
        return block

    def connect(self, src, dst):
        src = src if isinstance(src, tuple) else (src, 0)
        dst = dst if isinstance(dst, tuple) else (dst, 0)
        if not (0 <= src[1] < src[0].n_out):
            raise ValueError(f"{src[0].name} 에는 출력 포트 {src[1]} 가 없다")
        if not (0 <= dst[1] < dst[0].n_in):
            raise ValueError(f"{dst[0].name} 에는 입력 포트 {dst[1]} 가 없다")
        if dst in self.wires:
            raise ValueError(
                f"{dst[0].name} 입력 {dst[1]} 는 이미 {self.wires[dst][0].name} 와 연결됨")
        self.wires[dst] = src

    def compile(self):
        """블록 계산 순서 (위상 정렬). 대수 루프면 AlgebraicLoopError."""
        for b in self.blocks:
            for i in range(b.n_in):
                if (b, i) not in self.wires:
                    raise ValueError(f"{b.name} 의 입력 포트 {i} 가 연결되지 않음")
        deps = {b: set() for b in self.blocks}
        for dst, src in self.wires.items():
            if dst[0].feedthrough:               # 적분기는 순서 제약이 없다!
                deps[dst[0]].add(src[0])
        order, done = [], set()
        remaining = list(self.blocks)
        while remaining:
            ready = [b for b in remaining if deps[b] <= done]
            if not ready:
                cycle = " -> ".join(b.name for b in remaining)
                raise AlgebraicLoopError(f"대수 루프 발견 (적분기 없이 닫힌 고리): {cycle}")
            for b in ready:
                order.append(b)
                done.add(b)
                remaining.remove(b)
        return order


# ======================================================================
# 6주차 — 솔버 (오일러 / RK4)
# ======================================================================
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
    """2단계 평가: ①상태 블록(입력 불필요) ②feedthrough 블록(위상 순서)."""
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
            k1 = f(t, x)
            x = [xi + dt * d for xi, d in zip(x, k1)]
        else:                             # RK4 (정식 loopsym 과 동일)
            k1 = f(t, x)
            k2 = f(t + dt / 2, [xi + dt / 2 * k for xi, k in zip(x, k1)])
            k3 = f(t + dt / 2, [xi + dt / 2 * k for xi, k in zip(x, k2)])
            k4 = f(t + dt, [xi + dt * k for xi, k in zip(x, k3)])
            x = [xi + dt / 6 * (a + 2 * b_ + 2 * c + d)
                 for xi, a, b_, c, d in zip(x, k1, k2, k3, k4)]
    return bd
