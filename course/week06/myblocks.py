"""6주차 제공 — 완성 블록들 + Integrator (이번 주 TODO).

적분기가 상태(state)를 가진 첫 블록이다:
  y = x (상태를 그대로 출력),  dx/dt = u (입력이 곧 미분)
출력이 상태만으로 정해지므로 feedthrough=False — 고리를 끊는다.
"""

import math

# PyFunction 식에서 쓸 수 있는 안전한 이름들
_MATH_ENV = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
for _f in (abs, min, max):
    _MATH_ENV[_f.__name__] = _f


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


class Integrator(Block):
    """y = x,  dx/dt = u.  출력이 상태만으로 정해지므로 feedthrough=False."""

    n_in = 1
    state_size = 1
    feedthrough = False

    def __init__(self, x0=0.0, name=None):
        super().__init__(name)
        self.x0 = x0

    def initial(self):
        # TODO: 초기 상태 튜플 (x0 하나)
        raise NotImplementedError

    def output(self, t, u, x):
        # TODO: 상태를 그대로 출력 — u 는 쓰지 않는다! (그래서 고리가 끊긴다)
        raise NotImplementedError

    def derivative(self, t, u, x):
        # TODO: dx/dt = 입력
        raise NotImplementedError
