"""loopsym.blocks — 표준 블록 라이브러리.

Simulink 대응표:
  Constant, Step, Sine     <- Sources
  Gain, Sum, Saturation    <- Math Operations
  Integrator               <- Continuous
  TransferFunction         <- Continuous (Transfer Fcn)
  PyFunction               <- MATLAB Function 블록의 파이썬판
  Scope                    <- Sinks
"""

import math

from .core import Block

# PyFunction 의 식(expr) 안에서 쓸 수 있는 안전한 이름들
_MATH_ENV = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
for _f in (abs, min, max, sum, round, len):
    _MATH_ENV[_f.__name__] = _f


# ----------------------------------------------------------------------
# Sources — 입력 없이 신호를 만들어내는 블록
# ----------------------------------------------------------------------
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
        self.t_on = t_on
        self.height = height

    def output(self, t, u, x):
        return (self.height if t >= self.t_on else 0.0,)


class Sine(Block):
    n_in = 0

    def __init__(self, amp=1.0, freq_hz=1.0, phase=0.0, name=None):
        super().__init__(name)
        self.amp, self.freq_hz, self.phase = amp, freq_hz, phase

    def output(self, t, u, x):
        return (self.amp * math.sin(2 * math.pi * self.freq_hz * t + self.phase),)


# ----------------------------------------------------------------------
# 무상태 연산 블록 — feedthrough=True
# ----------------------------------------------------------------------
class Gain(Block):
    n_in = 1

    def __init__(self, k=1.0, name=None):
        super().__init__(name)
        self.k = k

    def output(self, t, u, x):
        return (self.k * u[0],)


class Sum(Block):
    """signs='+-' 처럼 부호 문자열로 입력 수와 부호를 정한다 (Simulink 와 동일)."""

    def __init__(self, signs="++", name=None):
        super().__init__(name)
        if not all(s in "+-" for s in signs):
            raise ValueError("signs 는 '+' 와 '-' 로만 구성")
        self.signs = signs
        self.n_in = len(signs)

    def output(self, t, u, x):
        return (sum(v if s == "+" else -v for s, v in zip(self.signs, u)),)


class Saturation(Block):
    n_in = 1

    def __init__(self, lo=-1.0, hi=1.0, name=None):
        super().__init__(name)
        self.lo, self.hi = lo, hi

    def output(self, t, u, x):
        return (min(max(u[0], self.lo), self.hi),)


class Product(Block):
    """ops='**' 처럼 곱(*)/나눗셈(/) 문자열로 입력 수와 연산을 정한다.

    Simulink 의 Product 블록과 동일: ops='*/' 이면 y = u0 / u1.
    """

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
    """MATLAB Function 블록의 파이썬판.

    세 가지 사용법:
      1) 식 문자열 — 입력은 u0, u1, ... 시간은 t, math 함수 사용 가능.
           PyFunction("4.0*u0 - 1.2*u1", n_in=2)
      2) 여러 줄 문장 — 출력을 y (단일) 또는 y0..y{n_out-1} 에 대입.
           PyFunction("e = u0 - u1\\ny0 = 3*e\\ny1 = 2*e", n_in=2, n_out=2)
         (뷰어에서 블록 더블클릭 → 코드 편집기로 작성)
      3) 파이썬 callable — func(t, u0, u1, ...) -> float 또는 tuple
           PyFunction(func=my_controller, n_in=2)
    문자열 방식(1, 2)은 다이어그램 뷰어(HTML)로 내보낼 때도 그대로 동작한다.
    """

    def __init__(self, expr=None, func=None, n_in=1, n_out=1, name=None):
        super().__init__(name)
        if (expr is None) == (func is None):
            raise ValueError("expr 또는 func 중 하나만 지정")
        self.expr, self.func = expr, func
        self.n_in, self.n_out = n_in, n_out
        if expr is not None:
            try:                    # 한 줄 식이면 eval, 아니면 문장(exec)으로
                self._code = compile(expr, f"<PyFunction {self.name}>", "eval")
                self._is_expr = True
            except SyntaxError:
                self._code = compile(expr, f"<PyFunction {self.name}>", "exec")
                self._is_expr = False

    def output(self, t, u, x):
        if self.func is not None:
            y = self.func(t, *u)
        elif self._is_expr:
            env = dict(_MATH_ENV, t=t, **{f"u{i}": v for i, v in enumerate(u)})
            y = eval(self._code, {"__builtins__": {}}, env)
        else:
            # 문장형: 전부 globals 로 실행 (locals 분리 시 컴프리헨션이 u0 를 못 봄)
            g = dict(_MATH_ENV, __builtins__={}, t=t,
                     **{f"u{i}": v for i, v in enumerate(u)})
            exec(self._code, g)
            if self.n_out == 1:
                y = g.get("y", g.get("y0"))
                if y is None:
                    raise ValueError(f"{self.name}: 문장형 코드는 출력을 y (또는 y0) 에 대입해야 함")
            else:
                missing = [f"y{i}" for i in range(self.n_out) if f"y{i}" not in g]
                if missing:
                    raise ValueError(f"{self.name}: 출력 {', '.join(missing)} 이 대입되지 않음")
                y = tuple(g[f"y{i}"] for i in range(self.n_out))
        return y if isinstance(y, tuple) else (y,)


# ----------------------------------------------------------------------
# 상태를 가진 블록 — 피드백 루프를 끊는 주인공들
# ----------------------------------------------------------------------
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


class TransferFunction(Block):
    """전달함수 num(s)/den(s) — 제어 가능 표준형(controllable canonical form).

    strictly proper (분자 차수 < 분모 차수) 만 허용해서 feedthrough=False 로
    두었다. D 항이 필요하면 Gain 을 병렬로 붙이면 된다 (수업 과제!).
    예: TransferFunction([1], [1, 2, 1])  ->  1/(s^2+2s+1)
    """

    n_in = 1
    feedthrough = False

    def __init__(self, num, den, name=None):
        super().__init__(name)
        if len(num) >= len(den):
            raise ValueError("strictly proper 전달함수만 지원 (len(num) < len(den))")
        d0 = float(den[0])
        self.den = [c / d0 for c in den]        # 최고차 계수 1 로 정규화
        self.num = [c / d0 for c in num]
        self.state_size = len(den) - 1
        # 상태 x[i] 는 출력의 i 계 미분에 대응 (x0=y 기본형).
        # num 은 내림차순 계수이므로 뒤집어서 x0 부터 매칭: y = b0·x0 + b1·x1 + ...
        self._c = list(reversed(self.num)) + [0.0] * (self.state_size - len(self.num))

    def output(self, t, u, x):
        # y = C x  (x 순서: 최고차 미분이 x[0])
        return (sum(c * xi for c, xi in zip(self._c, x)),)

    def derivative(self, t, u, x):
        # 동반 행렬(companion) 형태: x[i]' = x[i+1], 마지막 행이 -den 계수
        dx = list(x[1:])
        last = u[0] - sum(a * xi for a, xi in zip(reversed(self.den[1:]), x))
        return tuple(dx) + (last,)


# ----------------------------------------------------------------------
# 이산시간 블록 — sample_time 마다 update() 로 상태 갱신 (PX4 제어기는 전부 이산!)
# 샘플 사이 출력은 상수 유지 = ZOH 내장. feedthrough=False (출력이 xd 만으로 결정).
# ----------------------------------------------------------------------
class UnitDelay(Block):
    """y(k) = u(k-1).  z^-1."""

    n_in = 1
    dstate_size = 1
    feedthrough = False

    def __init__(self, st=0.01, x0=0.0, name=None):
        super().__init__(name)
        self.st = self.sample_time = st
        self.x0 = x0

    def dinitial(self):
        return (self.x0,)

    def output(self, t, u, x):
        return (x[0],)

    def update(self, t, u, xd):
        return (u[0],)


class DiscreteIntegrator(Block):
    """전진 오일러 누적: y(k) = st · Σ_{i<k} u(i).  전달함수 st/(z-1)."""

    n_in = 1
    dstate_size = 1
    feedthrough = False

    def __init__(self, st=0.01, x0=0.0, name=None):
        super().__init__(name)
        self.st = self.sample_time = st
        self.x0 = x0

    def dinitial(self):
        return (self.x0,)

    def output(self, t, u, x):
        return (x[0],)

    def update(self, t, u, xd):
        return (xd[0] + self.st * u[0],)


class DiscreteTransferFunction(Block):
    """z-영역 전달함수 num(z)/den(z) — strictly proper, 제어 가능 표준형.

    x(k+1) = A·x(k) + B·u(k),  y(k) = C·x(k).
    행렬 구조는 연속 TransferFunction 과 동일 (s 대신 z 라는 것만 다르다 —
    이 대칭이 수업 포인트)."""

    n_in = 1
    feedthrough = False

    def __init__(self, num, den, st=0.01, name=None):
        super().__init__(name)
        if len(num) >= len(den):
            raise ValueError("strictly proper 만 지원 (len(num) < len(den))")
        self.st = self.sample_time = st
        d0 = float(den[0])
        self.den = [c / d0 for c in den]
        self.num = [c / d0 for c in num]
        self.dstate_size = len(den) - 1
        self._c = list(reversed(self.num)) + [0.0] * (self.dstate_size - len(self.num))

    def output(self, t, u, x):
        return (sum(c * xi for c, xi in zip(self._c, x)),)

    def update(self, t, u, xd):
        nxt = list(xd[1:])
        nxt.append(u[0] - sum(a * xi for a, xi in zip(reversed(self.den[1:]), xd)))
        return tuple(nxt)


# ----------------------------------------------------------------------
# Mux / Demux — 벡터 신호 실험 (P14 스파이크; docs/spike_p14 참조)
# 규칙(v1): Mux 출력(튜플 신호)은 Demux 로만 소비한다. 연산 블록 투입 금지.
# ----------------------------------------------------------------------
class Mux(Block):
    """스칼라 n 개를 튜플 신호 1개로 묶는다."""

    def __init__(self, n_in=2, name=None):
        super().__init__(name)
        self.n_in = n_in

    def output(self, t, u, x):
        return (tuple(u),)


class Demux(Block):
    """튜플 신호를 스칼라 n 개로 푼다."""

    n_in = 1

    def __init__(self, n_out=2, name=None):
        super().__init__(name)
        self.n_out = n_out

    def output(self, t, u, x):
        v = u[0]
        if not isinstance(v, tuple) or len(v) != self.n_out:
            raise ValueError(f"{self.name}: 입력이 길이 {self.n_out} 튜플 신호가 아님 (Mux 출력을 연결)")
        return v


# ----------------------------------------------------------------------
# 서브시스템 — 다이어그램 안에 다이어그램
# ----------------------------------------------------------------------
class Inport(Block):
    """서브시스템 경계의 입력 표식. flatten 때 와이어로 치환되어 사라진다."""

    n_in = 0
    n_out = 1

    def __init__(self, index=0, name=None):
        super().__init__(name)
        self.index = index


class Outport(Block):
    """서브시스템 경계의 출력 표식."""

    n_in = 1
    n_out = 0

    def __init__(self, index=0, name=None):
        super().__init__(name)
        self.index = index


class Subsystem(Block):
    """내부 Diagram 을 하나의 블록처럼 쓴다. 실행 전에 flatten 으로 펼쳐진다.

    내부의 Inport/Outport 개수와 index 가 이 블록의 포트가 된다.
    feedthrough 는 자동 분석: 어떤 Inport 에서 어떤 Outport 까지
    feedthrough 블록만 거치는 경로가 하나라도 있으면 True.
    (내부가 적분기로 막혀 있으면 False — 그래서 plant 서브시스템을
    피드백 루프에 넣어도 대수 루프가 되지 않는다.)
    """

    def __init__(self, inner, params=None, name=None):
        super().__init__(name)
        self.inner = inner
        self.mask = dict(params or {})
        if self.mask:
            self._apply_mask(inner)
        self.inports = sorted(
            (b for b in inner.blocks if isinstance(b, Inport)), key=lambda b: b.index)
        self.outports = sorted(
            (b for b in inner.blocks if isinstance(b, Outport)), key=lambda b: b.index)
        for ports, kind in ((self.inports, "Inport"), (self.outports, "Outport")):
            if [p.index for p in ports] != list(range(len(ports))):
                raise ValueError(f"{self.name}: {kind} index 는 0 부터 빠짐없이 이어져야 함")
        self.n_in = len(self.inports)
        self.n_out = len(self.outports)
        self.feedthrough = self._analyze_feedthrough()

    def _apply_mask(self, d):
        """마스크 파라미터 치환 (Simulink mask 대응).

        내부 블록의 문자열 값 "$이름" 을 params["이름"] 으로 바꾼다.
        예: Gain(k="$Kp") 이 Subsystem(inner, params={"Kp": 3.0}) 에서 3.0 이 된다.
        생성 시점에 한 번 치환 — 중첩 서브시스템은 자기 마스크가 먼저 적용되어
        있으므로(먼저 생성됨), 남아 있는 "$이름" 만 바깥 마스크가 채운다."""
        for b in d.blocks:
            if isinstance(b, Subsystem):
                self._apply_mask(b.inner)
                continue
            for attr, val in list(vars(b).items()):
                if isinstance(val, str) and val.startswith("$") and val[1:] in self.mask:
                    setattr(b, attr, self.mask[val[1:]])
                    if attr == "st":            # sample_time 별칭 동기화
                        b.sample_time = self.mask[val[1:]]

    def _analyze_feedthrough(self):
        # Inport 에서 출발해 feedthrough 블록만 통과하며 Outport 도달 가능?
        from .core import Port
        fanout = {}   # block -> 다음 블록들
        for dst, src in self.inner.wires.items():
            fanout.setdefault(src.block, []).append(dst.block)
        frontier = list(self.inports)
        seen = set()
        while frontier:
            b = frontier.pop()
            for nxt in fanout.get(b, []):
                if nxt in seen:
                    continue
                if isinstance(nxt, Outport):
                    return True
                seen.add(nxt)
                if nxt.feedthrough:      # 상태 블록(1/s 등)에서 전파 중단
                    frontier.append(nxt)
        return False


# ----------------------------------------------------------------------
# Sinks
# ----------------------------------------------------------------------
class Scope(Block):
    """신호 기록계. 시뮬레이션의 매 스텝마다 입력을 저장한다."""

    n_out = 0
    feedthrough = True  # 기록만 하므로 순서상 마지막에 오도록

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
            if isinstance(v, tuple):
                raise ValueError(f"{self.name}: 벡터 신호는 Demux 로 풀어서 연결하세요")
            self.data[i].append(v)
