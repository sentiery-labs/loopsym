"""loopsym.estimation — 상태추정 팔레트 (CLD-P64, ARCHITECTURE §1 Estimation).

ComplementaryFilter <- px4_controller/nav/px4_ahrs_cf.m (Mahony 명시적 상보필터)

신호사슬이 완성된다: Sensors(IMU) → Estimation(CF) → Control → … → Plant.
11주차 하이라이트: IMU ideal→noisy 로 자세가 흔들리는 것을 목격 → 이 필터로
복구 — 상태추정이 왜 존재하는지를 체험한다.
"""

import math

from .core import Block
from .drone import _qmult, _qnorm


class ComplementaryFilter(Block):
    """Mahony 상보필터 AHRS: IMU 만으로 자세 + 바이어스 보정 각속도 추정.

    - 자이로 적분 = 고주파(빠른 회전) 추종
    - 가속도계 중력방향 보정(Kp) = 저주파 드리프트 제거 (tilt 고정)
    - 적분 보정(Ki) = 자이로 바이어스 추정
    yaw 는 가속도계로 관측 불가 → 자이로 적분 의존(완만 드리프트; 지자기/GPS 필요).

    입력: gyro p/q/r [0..2], accel x/y/z [3..5]  (IMU 블록 출력 순서와 동일)
    출력: q_est w/x/y/z [0..3], omega_est p/q/r [4..6] (바이어스 보정)
    이산상태(7): q(4), bhat(3).  출력은 xd(k) 기준 (loopsym 이산 규약 —
    MATLAB 판 대비 1샘플 지연, 폐루프 영향 무시 가능).
    """

    n_in = 6
    n_out = 7
    dstate_size = 7

    def __init__(self, kp=1.0, ki=0.05, st=0.004, name=None):
        super().__init__(name)
        self.kp, self.ki = kp, ki
        self.st = self.sample_time = st

    def dinitial(self):
        return (1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    @staticmethod
    def _tilt_error(q, accel):
        """e = cross(d_meas, d_est) — 추정 down 을 측정 down 으로 끌어당기는 body rate."""
        n = math.sqrt(sum(a * a for a in accel))
        if n < 1e-6:
            return (0.0, 0.0, 0.0)
        dm = [-a / n for a in accel]                       # 측정 down (body)
        w, x, y, z = q                                     # 추정 down = R(q)'·[0,0,1]
        de = (2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y))
        return (dm[1] * de[2] - dm[2] * de[1],
                dm[2] * de[0] - dm[0] * de[2],
                dm[0] * de[1] - dm[1] * de[0])

    def output(self, t, u, xd):
        q, bhat = xd[0:4], xd[4:7]
        return q + tuple(g - b for g, b in zip(u[0:3], bhat))

    def update(self, t, u, xd):
        dt = self.st
        q, bhat = list(xd[0:4]), xd[4:7]
        e = self._tilt_error(q, u[3:6])
        bhat = tuple(b - self.ki * ei * dt for b, ei in zip(bhat, e))
        omega = [g - b + self.kp * ei for g, b, ei in zip(u[0:3], bhat, e)]
        q = _qnorm(_qmult(q, [1.0, 0.5 * omega[0] * dt,
                              0.5 * omega[1] * dt, 0.5 * omega[2] * dt]))
        return tuple(q) + bhat
