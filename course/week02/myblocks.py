"""2주차 — 클래스로 블록 만들기.

"블록 = 파라미터를 품고(생성자), 신호를 변환하는(output) 객체".
Block 베이스와 Constant / Step 예시는 제공한다 — 규약을 눈으로 익힌 뒤
Gain, Saturation, Offset 세 블록을 완성하라.

규약 (모든 블록 공통):
  output(t, u, x) -> 출력 튜플 (길이 n_out)
    t : 현재 시각,  u : 입력 튜플 (길이 n_in),  x : 상태 (이번 주는 안 씀)
채점:  python -m pytest test_week02.py -q
"""


class Block:
    """모든 블록의 부모. 자식이 정하는 것: n_in / n_out / output()."""

    n_in = 0
    n_out = 1
    state_size = 0
    feedthrough = True          # 출력이 '지금 입력'에 즉시 의존하는가 (5주차에 중요)

    def __init__(self, name=None):
        self.name = name or type(self).__name__

    def __getitem__(self, i):
        """block[i] -> (block, i) 포트 튜플. 4주차 connect 에서 쓴다."""
        return (self, i)

    def output(self, t, u, x):
        return ()

    def derivative(self, t, u, x):     # 6주차에 쓴다
        return ()

    def initial(self):                 # 6주차에 쓴다
        return (0.0,) * self.state_size


class Constant(Block):
    """[예시] 항상 같은 값. 파라미터가 객체 속에 '산다'는 것을 보라."""

    n_in = 0

    def __init__(self, value=1.0, name=None):
        super().__init__(name)
        self.value = value

    def output(self, t, u, x):
        return (self.value,)


class Step(Block):
    """[예시] 1주차의 step 함수가 블록이 되면 이렇다."""

    n_in = 0

    def __init__(self, t_on=1.0, height=1.0, name=None):
        super().__init__(name)
        self.t_on, self.height = t_on, height

    def output(self, t, u, x):
        return (self.height if t >= self.t_on else 0.0,)


class Gain(Block):
    """y = k * u.  입력 1개."""

    n_in = 1

    def __init__(self, k=1.0, name=None):
        super().__init__(name)
        self.k = k

    def output(self, t, u, x):
        # TODO: 입력 u[0] 에 self.k 를 곱한 값을 튜플로 반환
        raise NotImplementedError


class Saturation(Block):
    """y = clip(u, lo, hi).  입력 1개."""

    n_in = 1

    def __init__(self, lo=-1.0, hi=1.0, name=None):
        # TODO: 부모 생성자 호출 + lo/hi 저장
        raise NotImplementedError

    def output(self, t, u, x):
        # TODO: u[0] 를 [lo, hi] 로 자른 값 반환 (min/max 사용)
        raise NotImplementedError


class Offset(Block):
    """y = u + c.  입력 1개 — 클래스 전체를 직접 설계하라 (과제)."""

    # TODO: n_in / __init__(c=0.0, name=None) / output 전부 작성
    pass
