"""3주차 — 인터페이스 규약의 힘.

지난주 블록들은 완성본으로 제공한다 (Block~Offset).
이번 주: "모든 블록이 같은 규약을 따르면 엔진은 블록 종류를 몰라도 된다."
문자열 파라미터로 포트 수가 정해지는 Sum/Product 와,
식 문자열을 실행하는 PyFunction 을 완성하라.

채점:  python -m pytest test_week03.py -q
"""

import math

# PyFunction 식에서 쓸 수 있는 안전한 이름들
_MATH_ENV = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
for _f in (abs, min, max):
    _MATH_ENV[_f.__name__] = _f


# ---------------------------------------------------------------- 지난주 완성본
class Block:
    n_in = 0
    n_out = 1
    state_size = 0
    feedthrough = True

    def __init__(self, name=None):
        self.name = name or type(self).__name__

    def __getitem__(self, i):
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
    n_in = 1

    def __init__(self, c=0.0, name=None):
        super().__init__(name)
        self.c = c

    def output(self, t, u, x):
        return (u[0] + self.c,)


# ---------------------------------------------------------------- 이번 주 TODO
class Sum(Block):
    """signs='+-' 부호 문자열이 입력 수와 부호를 정한다 (Simulink 와 동일).

    예: Sum('+-') 는 y = u0 - u1,  Sum('+--') 는 y = u0 - u1 - u2.
    """

    def __init__(self, signs="++", name=None):
        super().__init__(name)
        # TODO 1: signs 가 '+'/'-' 로만 되어 있는지 검사 — 아니면 ValueError
        # TODO 2: self.signs 저장, self.n_in = len(signs)
        raise NotImplementedError

    def output(self, t, u, x):
        # TODO 3: 부호를 적용해 전부 더한 값 반환
        raise NotImplementedError


class Product(Block):
    """ops='*/' 이면 y = u0 / u1.  '*' 와 '/' 로만 구성."""

    def __init__(self, ops="**", name=None):
        super().__init__(name)
        # TODO: 검증 + 저장 + n_in (Sum 과 같은 패턴)
        raise NotImplementedError

    def output(self, t, u, x):
        # TODO: 왼쪽부터 차례로 곱하거나 나눈다 (시작값 1.0)
        raise NotImplementedError


class PyFunction(Block):
    """식 문자열 블록 — MATLAB Function 블록의 파이썬판.

    식 안에서 쓸 수 있는 이름: u0, u1, ... (입력), t (시각), math 함수들.
    예: PyFunction("3.0*(u0-u1)", n_in=2)
    힌트: 생성자에서 compile(expr, "<이름>", "eval"),
          output 에서 eval(코드, {"__builtins__": {}}, 환경dict).
    """

    def __init__(self, expr, n_in=1, n_out=1, name=None):
        super().__init__(name)
        self.expr = expr
        self.n_in, self.n_out = n_in, n_out
        # TODO: self._code = compile(...)
        raise NotImplementedError

    def output(self, t, u, x):
        # TODO: _MATH_ENV + t + u0..u{n-1} 환경을 만들어 eval.
        #       결과가 튜플이면 그대로, 스칼라면 1-튜플로.
        raise NotImplementedError


class Scope(Block):
    """[제공] 신호 기록계 — 6주차 솔버가 record() 를 불러 준다."""

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
