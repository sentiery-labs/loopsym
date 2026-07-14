"""4주차 — 다이어그램 = 그래프, 실행 순서 = 위상 정렬.

와이어를 자료구조로: wires = { (dst블록, dst포트): (src블록, src포트) }
"입력 포트당 드라이버는 하나" — 이 불변식이 모든 검증의 뿌리다.

이번 주 가정: 모든 블록이 feedthrough (적분기는 다음 주).
채점:  python -m pytest test_week04.py -q
"""


class Diagram:
    def __init__(self):
        self.blocks = []
        self.wires = {}          # (dst_block, dst_idx) -> (src_block, src_idx)

    def add(self, block):
        self.blocks.append(block)
        return block

    def connect(self, src, dst):
        """src 출력 포트 -> dst 입력 포트. 블록을 그대로 주면 0번 포트."""
        src = src if isinstance(src, tuple) else (src, 0)
        dst = dst if isinstance(dst, tuple) else (dst, 0)
        # TODO 1: src[1] 이 src[0].n_out 범위를 벗어나면 ValueError
        # TODO 2: dst[1] 이 dst[0].n_in 범위를 벗어나면 ValueError
        # TODO 3: dst 가 이미 연결되어 있으면 ValueError ("이미 ... 연결됨")
        # TODO 4: self.wires 에 등록
        raise NotImplementedError

    def compile(self):
        """블록 계산 순서를 반환 (위상 정렬, Kahn).

        규칙: 어떤 블록의 입력을 주는 블록은 그 블록보다 먼저 와야 한다.
        (이번 주는 전부 feedthrough 라고 가정 — 고리가 있으면 RuntimeError.)
        """
        # TODO 1: 모든 블록의 모든 입력 포트가 연결됐는지 검사 — 아니면 ValueError
        # TODO 2: deps[블록] = {그 블록에 입력을 주는 블록들} 구성
        # TODO 3: Kahn — deps 가 전부 처리된 블록부터 order 에 추가.
        #         진행이 안 되는데 남아 있으면 RuntimeError("고리") (다음 주에 정식화)
        raise NotImplementedError
