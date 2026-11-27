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


class Rangefinder(SensorBlock):
    """아래 방향 거리계(라이다·초음파 고도계): 기체 아래축(FRD +z) 광선의 거리.

    입력: QuadPlant 출력 13개 (q 0..3 | pqr 4..6 | pN pE pD 7..9 | vel 10..12)
    출력: range_m [0], valid(0/1) [1].  무효면 (max_range, 0).
    포트는 fidelity 와 무관하게 불변 (ARCHITECTURE §2).

      ideal : 평평한 지면(pD = 0) 가정. 거리 = 고도 / cos(기울기).
              광선이 수평보다 위를 향하거나 max_range 를 넘으면 무효. 지면 위면 (0, 1).
      noisy : ideal + 샘플마다 N(0, noise_sd) (유효할 때만, 0 아래는 0). seed 로 재현.
      world : link 로 찾은 WorldLink 의 마지막 frame 값(range_m, range_valid).
              3D 월드의 건물·지형까지 잰다. 한 샘플 늦고, 첫 샘플은 무효.
    link: WorldLink 이름. 비우면 다이어그램의 유일한 WorldLink (서브시스템 안 포함).
    """

    supported_fidelity = ("ideal", "noisy", "world")
    n_in = 13
    n_out = 2
    dstate_size = 1             # 유지 잡음 (noisy)

    def __init__(self, fidelity="ideal", max_range=100.0, noise_sd=0.02, seed=0,
                 st=0.04, link="", name=None):
        super().__init__(fidelity, seed, st, name)
        self.max_range = float(max_range)
        self.noise_sd = float(noise_sd)
        self.link = link
        self._link = None

    def resolve_links(self, blocks):
        if self.fidelity != "world":
            return
        from .world import find_link        # world.py 가 이 모듈을 임포트하므로 지연 임포트
        link = find_link(blocks, self.link)
        if link.rangefinder is not None and link.rangefinder is not self:
            raise ValueError(
                f"{self.name}: {link.name} 에 거리계가 이미 있습니다({link.rangefinder.name}) — "
                "WorldLink 하나에 world 거리계는 하나")
        link.rangefinder = self
        self._link = link

    def _invalid(self):
        return (self.max_range, 0.0)

    def output(self, t, u, xd):
        if self.fidelity == "world":
            f = self._link.latest if self._link is not None else None
            if f is None or not f.get("range_valid") or f.get("range_m") is None:
                return self._invalid()
            r = float(f["range_m"])
            return (r, 1.0) if 0.0 <= r <= self.max_range else self._invalid()

        qw, qx, qy, qz = u[0:4]
        down = 1.0 - 2.0 * (qx * qx + qy * qy)      # R(q)·[0,0,1] 의 D 성분 = cos(기울기)
        if down <= 1e-6:
            return self._invalid()                   # 광선이 수평이거나 위를 향함
        h = -u[9]
        if h <= 0.0:
            return (0.0, 1.0)
        r = h / down
        if r > self.max_range:
            return self._invalid()
        if self.fidelity == "noisy":
            r = max(0.0, r + xd[0])
        return (r, 1.0)

    def update(self, t, u, xd):
        return (self._gauss(self.noise_sd),) if self.fidelity == "noisy" else (0.0,)
