"""2주차 정답 — myblocks.py 대체용."""

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
