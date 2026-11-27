"""loopsym.sensors — 센서 팔레트 + 공통 규약 (CLD-P62, ARCHITECTURE §2).

핵심 설계: **같은 센서 블록이 fidelity 파라미터 하나로 충실도를 올린다.
포트 시그니처는 절대 불변** — "시뮬레이션에서 실기체까지, 다이어그램은 하나."

  fidelity = "ideal"    : plant 상태 그대로 통과 (진리값)
             "noisy"    : bias + 백색잡음(noise density) 수식 모델
             "world"    : 3D 월드 시뮬레이터(SENTIERY) 연동 — WorldLink 로 받은 값
             "hardware" : 예약 (P41/P43 — MAVLink 수신으로 교체)

센서마다 지원하는 충실도는 클래스 속성 supported_fidelity 에 적는다
(기본 ideal/noisy). 지원하지 않는 단계를 고르면 NotImplementedError.

noisy 잡음은 seed 로 고정 가능 (자동채점/회귀 테스트용). 잡음은 샘플
시점(update)마다 1회 생성해 이산상태로 유지 — RK4 minor step 이나 재실행
横断으로 재현 가능하다 (dinitial 이 RNG 를 seed 로 리셋).
"""

import math
import random

from .core import Block

_FIDELITY = ("ideal", "noisy", "world", "hardware")


class SensorBlock(Block):
    """센서 공통 베이스: fidelity 검증 + 시드 고정 RNG + 샘플타임."""

    supported_fidelity = ("ideal", "noisy")   # 하위 클래스가 덮어쓴다

    def __init__(self, fidelity="ideal", seed=0, st=0.004, name=None):
        super().__init__(name)
        if fidelity not in _FIDELITY:
            raise ValueError(f"fidelity 는 {_FIDELITY} 중 하나: {fidelity!r}")
        supported = type(self).supported_fidelity
        if fidelity not in supported:
            raise NotImplementedError(
                f"{type(self).__name__}: fidelity={fidelity!r} 는 지원하지 않음 — 지원: {supported}")
        self.fidelity = fidelity
        self.seed = seed
        self.st = self.sample_time = st
        self._rng = random.Random(seed)

    def dinitial(self):
        self._rng = random.Random(self.seed)      # 재실행 재현성 (회귀/채점)
        return super().dinitial()

    def _gauss(self, sigma):
        return self._rng.gauss(0.0, sigma) if sigma > 0 else 0.0


class IMU(SensorBlock):
    """관성센서: 자이로(각속도) + 가속도계(비력, PX4 규약 — 레벨에서 [0,0,−g]).

    입력: q(4) [0..3], omega p/q/r [4..6], vel N/E/D [7..9]   (플랜트 상태)
    출력: gyro p/q/r [0..2], accel x/y/z [3..5]  (동체축)
    포트는 fidelity 와 무관하게 불변 (ARCHITECTURE §2).

    noisy 모델: 출력 = 참값 + bias + N(0, σ),  σ = density·√(1/(2·st))
    (백색잡음 밀도 × √대역폭; 기본값 ≈ ICM-42688 datasheet 급).
    가속도계 비력은 (vel−vel_prev)/st 의 이산미분 − 중력을 동체축으로 회전.
    이산상태(9): vel_prev(3), 유지 잡음 gyro(3)+accel(3).
    """

    n_in = 10
    n_out = 6
    dstate_size = 9

    def __init__(self, fidelity="ideal", gyro_bias=0.0, gyro_nd=5e-5,
                 accel_bias=0.0, accel_nd=7e-4, g=9.81,
                 seed=0, st=0.004, name=None):
        super().__init__(fidelity, seed, st, name)
        self.gyro_bias, self.gyro_nd = gyro_bias, gyro_nd      # [rad/s], [rad/s/√Hz]
        self.accel_bias, self.accel_nd = accel_bias, accel_nd  # [m/s²], [m/s²/√Hz]
        self.g = g

    def output(self, t, u, xd):
        omega = u[4:7]
        if self.fidelity == "ideal":
            gyro = omega
        else:
            gyro = tuple(w + self.gyro_bias + n for w, n in zip(omega, xd[3:6]))

        # 비력 f_body = R(q)ᵀ · (a_ned − g_ned),  a_ned = (vel − vel_prev)/st
        qw, qx, qy, qz = u[0:4]
        a = [(v - vp) / self.st for v, vp in zip(u[7:10], xd[0:3])]
        a[2] -= self.g
        # Rᵀ (NED -> body)
        f = (a[0] * (1 - 2*(qy*qy + qz*qz)) + a[1] * 2*(qx*qy + qw*qz) + a[2] * 2*(qx*qz - qw*qy),
             a[0] * 2*(qx*qy - qw*qz) + a[1] * (1 - 2*(qx*qx + qz*qz)) + a[2] * 2*(qy*qz + qw*qx),
             a[0] * 2*(qx*qz + qw*qy) + a[1] * 2*(qy*qz - qw*qx) + a[2] * (1 - 2*(qx*qx + qy*qy)))
        if self.fidelity == "noisy":
            f = tuple(fi + self.accel_bias + n for fi, n in zip(f, xd[6:9]))
        return gyro + f

    def update(self, t, u, xd):
        sg = self.gyro_nd * math.sqrt(0.5 / self.st)
        sa = self.accel_nd * math.sqrt(0.5 / self.st)
        return (tuple(u[7:10])
                + tuple(self._gauss(sg) for _ in range(3))
                + tuple(self._gauss(sa) for _ in range(3)))
