"""5주차 — 피드백과 대수 루프.

지난주 Diagram 은 고리를 만나면 무조건 에러였다. 하지만 제어는 피드백
(고리!)이 본질이다. 열쇠는 feedthrough:
  · Gain 의 출력은 '지금 입력'이 필요하다 → 순서 제약 있음
  · 상태 블록(적분기)의 출력은 '과거의 누적'이다 → 입력을 기다릴 필요 없음
    → 고리를 끊는다!
feedthrough 블록끼리만 이루는 고리 = 답이 없는 연립 = 대수 루프 → 에러.

connect 와 미연결 검사는 지난주 완성본을 제공한다.
채점:  python -m pytest test_week05.py -q
"""


class AlgebraicLoopError(Exception):
    """feedthrough 블록끼리 고리를 이루면 계산 순서를 정할 수 없다."""


class Diagram:
    def __init__(self):
        self.blocks = []
        self.wires = {}

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
        """블록 계산 순서. feedthrough=False 블록이 고리를 끊는다."""
        for b in self.blocks:
            for i in range(b.n_in):
                if (b, i) not in self.wires:
                    raise ValueError(f"{b.name} 의 입력 포트 {i} 가 연결되지 않음")

        # TODO 1: deps 구성 — 단, **dst 블록이 feedthrough 일 때만** 제약을 건다.
        #         (feedthrough=False 블록은 아무 순서 제약이 없다 — 이 한 줄이
        #          피드백을 가능하게 하는 전부다!)
        # TODO 2: Kahn 위상 정렬 — 진행이 안 되는데 블록이 남아 있으면
        #         AlgebraicLoopError 를 raise. 메시지에 남은 블록 이름들을
        #         " -> " 로 이어 넣어라 (디버깅 배려 — 어디가 고리인지 보이게).
        raise NotImplementedError
