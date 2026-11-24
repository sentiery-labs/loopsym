"""loopsym.sim — 고정 스텝 솔버 (RK4).

Simulink 의 ode4 (Runge-Kutta, fixed-step) 에 해당한다.

동작 원리:
  1. 모든 블록의 상태를 하나의 벡터 x 로 이어붙인다.
  2. eval_outputs(t, x): compile() 이 정한 순서대로 블록 출력을 계산해서
     "어느 와이어에 어떤 값이 흐르는지"를 채운다.
  3. deriv(t, x): 출력이 다 계산된 뒤 상태 블록들의 미분을 모아 dx 를 만든다.
  4. RK4 로 x 를 한 스텝 전진. Scope 는 큰 스텝(major step)에서만 기록한다.

샘플 시간 규칙 (Simulink 와 동일):
  sample_time 이 있는 블록(이산 블록, ZeroOrderHold, 이산 제어기)은 자기 샘플
  시점의 major step 에서만 출력을 계산한다. 그 사이 — 다음 base step 들과
  RK4 minor step — 에는 직전 출력을 그대로 낸다(ZOH). 그래서 st > dt 인
  멀티레이트에서도 이산 출력이 정확히 st 간격으로 바뀌고, feedthrough 이산
  블록(PID 등)이 minor step 의 입력으로 다시 계산되는 일이 없다.
"""

from .core import Diagram, Port
from .blocks import Scope, Subsystem, Inport, Outport


def flatten(bd):
    """서브시스템을 전부 펼쳐 실제 블록만 남은 평평한 Diagram 을 만든다.

    Simulink 도 (virtual) subsystem 을 컴파일 때 이렇게 펼친다.
    Inport/Outport 는 '와이어 이음새'일 뿐이므로 따라가서 제거한다.
    블록 인스턴스는 복사하지 않고 그대로 쓴다 — 안쪽 Scope 도 그대로 기록된다.
    """
    flat = Diagram()
    parent = {}   # 내부 Diagram -> (그걸 품은 Subsystem, Subsystem 이 놓인 Diagram)

    def collect(d):
        for b in d.blocks:
            if isinstance(b, Subsystem):
                parent[b.inner] = (b, d)
                collect(b.inner)
            elif not isinstance(b, (Inport, Outport)):
                flat.blocks.append(b)
    collect(bd)

    def resolve(src, d):
        """경계 표식을 따라가 진짜 소스 포트를 찾는다."""
        b = src.block
        if isinstance(b, Subsystem):                 # 서브시스템의 출력 = 내부 Outport 의 드라이버
            op = b.outports[src.index]
            inner_src = b.inner.wires.get(Port(op, 0))
            if inner_src is None:
                raise ValueError(f"'{b.name}' 내부의 {op.name}(Outport {src.index}) 가 연결되지 않음")
            return resolve(inner_src, b.inner)
        if isinstance(b, Inport):                    # 내부 Inport = 바깥에서 들어온 와이어
            if d not in parent:
                raise ValueError(f"최상위 다이어그램의 '{b.name}'(Inport) 는 소스가 없음")
            sub, pd = parent[d]
            outer_src = pd.wires.get(Port(sub, b.index))
            if outer_src is None:
                raise ValueError(f"'{sub.name}' 의 입력 포트 {b.index} 가 연결되지 않음")
            return resolve(outer_src, pd)
        return src

    def rewire(d):
        for dst, src in d.wires.items():
            if not isinstance(dst.block, (Subsystem, Outport)):
                flat.wires[dst] = resolve(src, d)
        for b in d.blocks:
            if isinstance(b, Subsystem):
                rewire(b.inner)
    rewire(bd)
    return flat


class Simulator:
    def __init__(self, diagram):
        self.bd = flatten(diagram)
        diagram = self.bd
        self.order = diagram.compile()
        # 연속 상태 벡터에서 각 블록이 차지하는 구간 [ofs, ofs+size)
        self.offsets, ofs = {}, 0
        for b in diagram.blocks:
            self.offsets[b] = ofs
            ofs += b.state_size
        self.n_states = ofs
        # 이산 상태: 블록별 튜플 (RK4 벡터와 분리 — 적분되지 않는다)
        self.discrete = [b for b in diagram.blocks if b.dstate_size]
        self.xd = {}
        # 샘플 블록: sample_time 이 있는 블록 (이산 상태가 없어도 — 예: ZeroOrderHold)
        self.sampled = [b for b in diagram.blocks if b.sample_time is not None]
        self._held = {}     # 샘플 블록의 마지막 출력 — 샘플 사이에 그대로 낸다

    def _initial_state(self):
        x = [0.0] * self.n_states
        for b in self.bd.blocks:
            for i, v in enumerate(b.initial()):
                x[self.offsets[b] + i] = v
        return x

    def _block_state(self, b, x):
        o = self.offsets[b]
        return tuple(x[o:o + b.state_size])

    def _block_output(self, b, t, u, x, hits):
        """블록 하나의 출력. 샘플 블록은 샘플 시점(hits)에만 계산하고, 그 밖에는
        직전 출력을 그대로 낸다 = ZOH. 이산 블록이면 x 자리에 이산 상태."""
        if b.sample_time is not None and b not in hits:
            return self._held[b]
        xs = self.xd[b] if b.dstate_size else self._block_state(b, x)
        y = b.output(t, u, xs)
        if b.sample_time is not None:
            self._held[b] = y
        return y

    def _eval_outputs(self, t, x, hits=frozenset()):
        """블록 출력 계산. 반환: ({Port: 값}, {블록: 입력 튜플})

        hits: 이 major step 에서 샘플 시점인 블록들. 기본값(빈 집합)은 RK4
        minor step — 샘플 블록은 전부 붙잡아 둔 출력을 낸다.

        Simulink 와 같은 2단계:
          1) feedthrough=False 블록 — 출력이 상태 x 만으로 결정되므로
             입력 없이도 먼저 전부 계산할 수 있다 (이래서 루프가 끊긴다!)
          2) feedthrough=True 블록 — compile() 이 정한 순서대로 계산
        """
        signals = {}
        for b in self.bd.blocks:
            if not b.feedthrough:
                y = self._block_output(b, t, None, x, hits)
                for i, v in enumerate(y):
                    signals[Port(b, i)] = v
        for b in self.order:
            if b.feedthrough:
                u = tuple(signals[self.bd.wires[Port(b, i)]] for i in range(b.n_in))
                y = self._block_output(b, t, u, x, hits)
                for i, v in enumerate(y):
                    signals[Port(b, i)] = v
        # 모든 신호가 정해진 뒤에야 각 블록의 입력 튜플을 만들 수 있다
        # (Integrator 의 입력 = 미분 계산에 필요)
        inputs = {
            b: tuple(signals[self.bd.wires[Port(b, i)]] for i in range(b.n_in))
            for b in self.bd.blocks
        }
        return signals, inputs

    def _deriv(self, t, x):
        _, inputs = self._eval_outputs(t, x)
        dx = [0.0] * self.n_states
        for b in self.bd.blocks:
            if b.state_size:
                d = b.derivative(t, inputs[b], self._block_state(b, x))
                for i, v in enumerate(d):
                    dx[self.offsets[b] + i] = v
        return dx

    def run(self, t_end, dt=0.01):
        """0 부터 t_end 까지 고정 스텝 dt 로 시뮬레이션."""
        for _ in self.iter_run(t_end, dt):
            pass
        return self

    def iter_run(self, t_end, dt=0.01):
        """run() 의 제너레이터 판 — 매 major step 이 끝난 뒤 (step, t) 를 yield.

        스텝 사이에 다른 일을 끼워야 하는 호출자용: 서버 모드의 결과
        스트리밍/정지 확인, 실시간 러너의 페이싱 등. run() 과 의미론이
        완전히 같다 (run 자체가 이 제너레이터를 소비한다)."""
        x = self._initial_state()
        self.xd = {b: tuple(b.dinitial()) for b in self.discrete}
        self._held = {}
        # 샘플 블록의 sample_time 은 dt 의 정수배여야 한다 (Simulink 의 rate 규칙)
        period = {}
        for b in self.sampled:
            m = b.sample_time / dt
            if b.sample_time <= 0 or abs(m - round(m)) > 1e-6:
                raise ValueError(
                    f"{b.name}: sample_time({b.sample_time})은 dt({dt})의 양의 정수배여야 함")
            period[b] = round(m)
        n = round(t_end / dt)
        for step in range(n + 1):
            t = step * dt          # 누적 덧셈 대신 곱셈 — 부동소수점 드리프트 방지
            # --- major step: 출력 계산, Scope 기록 ---
            # step 0 은 모든 샘플 블록의 샘플 시점이라 _held 가 여기서 채워진다
            hits = {b for b in self.sampled if step % period[b] == 0}
            _, inputs = self._eval_outputs(t, x, hits)
            for b in self.bd.blocks:
                if isinstance(b, Scope):
                    b.record(t, inputs[b])

            # --- RK4 한 스텝 (연속 상태만) ---
            # 이산 출력은 이 구간 [t, t+dt) 동안 y(k)=f(xd(k)) 로 상수 = ZOH.
            # 그래서 update 는 반드시 RK4 "다음"에 한다 — 먼저 하면 연속 적분이
            # 한 샘플 이른 값 xd(k+1) 을 보게 된다.
            k1 = self._deriv(t, x)
            k2 = self._deriv(t + dt / 2, [xi + dt / 2 * k for xi, k in zip(x, k1)])
            k3 = self._deriv(t + dt / 2, [xi + dt / 2 * k for xi, k in zip(x, k2)])
            k4 = self._deriv(t + dt, [xi + dt * k for xi, k in zip(x, k3)])
            x = [
                xi + dt / 6 * (a + 2 * b_ + 2 * c + d)
                for xi, a, b_, c, d in zip(x, k1, k2, k3, k4)
            ]

            # --- 샘플 시점인 이산 블록 상태 갱신: xd(k) → xd(k+1), 입력은 u(t_k) ---
            # 새 상태의 출력은 다음 샘플 시점에 나온다 (그 전까진 _held 유지)
            for b in self.discrete:
                if b in hits:
                    self.xd[b] = tuple(b.update(t, inputs[b], self.xd[b]))

            yield step, t


def run(diagram, t_end, dt=0.01):
    """편의 함수: Simulator(bd).run(...)"""
    return Simulator(diagram).run(t_end, dt)
