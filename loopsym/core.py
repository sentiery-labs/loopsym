"""loopsym.core — 블록 다이어그램의 뼈대.

Simulink 가 하는 일을 최소한으로 흉내낸다:
  1. Block  : 입력 포트 / 출력 포트 / (필요하면) 내부 상태를 가진 객체
  2. Diagram: 블록들을 담고, 와이어(연결)를 기록
  3. compile: 매 스텝마다 블록을 어떤 순서로 계산할지 결정 (위상 정렬)
              + 대수 루프(algebraic loop) 검출

신호는 전부 스칼라(float) 하나로 제한한다 — 수업용 단순화.
"""

from collections import namedtuple

# 와이어의 끝점: (어떤 블록의, 몇 번째 포트). block[i] 로 만든다.
Port = namedtuple("Port", ["block", "index"])


class Block:
    """모든 블록의 부모 클래스.

    자식 클래스가 정하는 것:
      n_in        : 입력 포트 수
      n_out       : 출력 포트 수
      state_size  : 내부 상태(적분되는 값)의 개수. 0 이면 무상태 블록.
      feedthrough : 출력이 '지금 이 순간의 입력'에 즉시 의존하는가?
                    Gain 은 True (y = k*u), Integrator 는 False (y = x).
                    False 인 블록이 피드백 루프를 끊어 준다 — Simulink 와 동일.
    구현하는 메서드:
      output(t, u, x)     -> 출력 튜플 (길이 n_out)
      derivative(t, u, x) -> 상태 미분 튜플 (길이 state_size)
      initial()           -> 초기 상태 튜플
    """

    n_in = 0
    n_out = 1
    state_size = 0          # 연속 상태 (RK4 로 적분됨)
    dstate_size = 0         # 이산 상태 (sample_time 마다 update() 로 갱신)
    sample_time = None      # None = 연속 블록. 숫자면 k·sample_time 마다 update()
    feedthrough = True

    _counter = {}

    def __init__(self, name=None):
        cls = type(self).__name__
        Block._counter[cls] = Block._counter.get(cls, 0) + 1
        self.name = name or f"{cls}{Block._counter[cls]}"

    def __getitem__(self, i):
        """block[i] -> i 번째 포트. connect() 에서 입력/출력 양쪽에 쓴다."""
        return Port(self, i)

    def output(self, t, u, x):
        return ()

    def derivative(self, t, u, x):
        return ()

    def initial(self):
        return (0.0,) * self.state_size

    # ---- 이산 블록용 (dstate_size > 0 인 블록만 구현) ----
    def dinitial(self):
        return (0.0,) * self.dstate_size

    def update(self, t, u, xd):
        """샘플 시점 t = k·sample_time 에서 다음 이산 상태를 반환.

        Simulink 와 같은 순서: 그 시점의 출력(y = f(xd))을 먼저 내보낸 뒤
        update 가 호출된다. 즉 y(k) 는 xd(k), update 는 xd(k+1) 을 만든다.
        샘플 사이 구간에서 출력은 상수로 유지된다 (ZOH 는 내장 동작)."""
        return xd

    # ---- 바깥 세계와 이어지는 블록용 (WorldLink, 센서의 world 충실도 등) ----
    def resolve_links(self, blocks):
        """Simulator 를 만들 때 한 번 불린다. blocks = 서브시스템을 펼친 뒤의
        실제 블록 전부. 다른 블록을 이름으로 찾아 묶어 둘 때 쓴다."""

    def finish(self):
        """실행이 어떻게 끝나든(정상·예외·중간 정지) 그 실행마다 한 번 불린다.
        접속을 닫는 등 뒷정리를 여기서 한다."""

    def __repr__(self):
        return f"<{type(self).__name__} '{self.name}'>"


class AlgebraicLoopError(Exception):
    """무상태(feedthrough) 블록끼리 고리를 이루면 계산 순서를 정할 수 없다."""


class Diagram:
    """블록 + 와이어의 모음. Simulink 의 모델(.slx) 에 해당."""

    def __init__(self):
        self.blocks = []
        # 입력 포트 하나당 드라이버는 하나: {(dst_block, dst_idx): (src_block, src_idx)}
        self.wires = {}

    def add(self, block):
        self.blocks.append(block)
        return block

    def connect(self, src, dst):
        """src 의 출력 포트 -> dst 의 입력 포트.

        블록을 그대로 주면 0 번 포트로 간주한다.
          bd.connect(step, err[0])   # step 출력 0 -> err 입력 0
          bd.connect(plant, err[1])  # 피드백
        """
        src = src if isinstance(src, Port) else Port(src, 0)
        dst = dst if isinstance(dst, Port) else Port(dst, 0)
        if not (0 <= src.index < src.block.n_out):
            raise ValueError(f"{src.block.name} 에는 출력 포트 {src.index} 가 없다")
        if not (0 <= dst.index < dst.block.n_in):
            raise ValueError(f"{dst.block.name} 에는 입력 포트 {dst.index} 가 없다")
        if dst in self.wires:
            old = self.wires[dst]
            raise ValueError(
                f"{dst.block.name} 입력 {dst.index} 는 이미 {old.block.name} 와 연결됨"
            )
        self.wires[dst] = src

    # ------------------------------------------------------------------
    # compile: 실행 순서 결정
    # ------------------------------------------------------------------
    def compile(self):
        """블록 계산 순서를 반환한다.

        규칙: feedthrough 블록은 자기 입력을 주는 블록보다 '나중에' 계산해야
        한다. Integrator 처럼 feedthrough=False 인 블록은 출력이 상태 x 만으로
        결정되므로 언제 계산해도 되고 — 그래서 피드백 고리를 끊는다.
        """
        # 1) 연결 검사: 안 이어진 입력 포트는 에러 (Simulink 의 미연결 경고)
        for b in self.blocks:
            for i in range(b.n_in):
                if Port(b, i) not in self.wires:
                    raise ValueError(f"{b.name} 의 입력 포트 {i} 가 연결되지 않음")

        # 2) 의존 그래프: src -> dst (dst 가 feedthrough 일 때만 순서 제약)
        deps = {b: set() for b in self.blocks}   # b 가 먼저 필요로 하는 블록들
        for dst, src in self.wires.items():
            if dst.block.feedthrough:
                deps[dst.block].add(src.block)

        # 3) 위상 정렬 (Kahn) — 남은 블록이 있는데 진행이 안 되면 대수 루프
        order, done = [], set()
        remaining = list(self.blocks)
        while remaining:
            ready = [b for b in remaining if deps[b] <= done]
            if not ready:
                cycle = " -> ".join(b.name for b in remaining)
                raise AlgebraicLoopError(
                    f"대수 루프 발견 (적분기 없이 닫힌 고리): {cycle}"
                )
            for b in ready:
                order.append(b)
                done.add(b)
                remaining.remove(b)
        return order
