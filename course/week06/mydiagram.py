"""6주차 제공 — 5주차에 완성한 Diagram (대수 루프 검출 포함). 학생 파일명이 mydiagram.py 이므로 그대로 복사해 써도 된다."""

import math

# PyFunction 식에서 쓸 수 있는 안전한 이름들
_MATH_ENV = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
for _f in (abs, min, max):
    _MATH_ENV[_f.__name__] = _f


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
