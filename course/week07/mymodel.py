"""7주차 — 폐루프 완성 + ★브리지★: 내 엔진 ↔ 진짜 loopsym.

mybs.py = 1~6주차에 우리가 만든 미니 엔진의 완성본 (제공).
이번 주는 그 엔진으로 제어 루프를 '닫는' 주다. 아래 두 모델을 완성하라.
채점기가 같은 모델을 정식 loopsym 으로도 돌려 6자리까지 대조한다 —
숫자가 같으면, 네가 만든 엔진은 진짜다.

채점:  python -m pytest test_week07.py -q
"""

import mybs


def build_pi_loop():
    """PI 폐루프 (정식판 예제 ex1 과 같은 문제).

          +------+  e   +---------------------+  u  +--------------+
    ref ->| Sum  |----->| Kp=3  +  Ki=2 * ∫e  |---->| 1/(s²+2s+1)  |--+--> scope
      +-->|  +-  |      +---------------------+     +--------------+  |
      |                                                               |
      +---------------------------------------------------------------+

    ref = Step(t_on=1.0, height=1.0)
    플랜트 1/(s²+2s+1) 는 전달함수 블록이 없으므로 미분방정식으로 푼다:
        ẍ = u - 2·ẋ - x
    → Sum("+--") 하나, Integrator 둘(ẋ, x), 감쇠 경로에 Gain(2.0).

    반환: (bd, scope) — scope 는 플랜트 출력 x 를 기록하는 1채널 Scope.
    """
    bd = mybs.Diagram()
    # TODO: 블록 생성(add) → 배선(connect) → (bd, scope) 반환
    #   힌트: 다이어그램 그림의 화살표 하나가 connect 한 줄이다.
    #   포트 여러 개인 블록은 sum[0], sum[1] 처럼 포트를 지정.
    raise NotImplementedError


def build_pendulum():
    """비선형 진자 + PD (정식판 예제 ex2 와 같은 문제) — 과제.

    동역학:  θ'' = -(9.81/1.0)·sin(θ) - 0.3·θ' + u   → PyFunction(n_in=3)
    제어기:  u = 6.0·(ref - θ) - 2.0·θ'              → PyFunction(n_in=3)
    ref = Step(t_on=1.0, height=0.8),  적분기 둘(θ'' → θ' → θ).

    반환: (bd, scope) — scope 는 θ 를 기록하는 1채널 Scope.
    [관찰] θ 는 0.8 에 못 미치고 ~0.31 rad 에 머문다 — 중력을 이기려면
    정상상태에서도 u ≠ 0 이어야 하는데 PD 는 오차가 있어야만 토크를 낸다.
    "왜 적분항(I)이 필요한가"의 실물 증거다 (가산 과제: I 를 추가해 보라).
    """
    bd = mybs.Diagram()
    # TODO
    raise NotImplementedError
