"""loopsym.drone — 드론 팔레트: Plant / Control / Allocation (CLD-P65).

PX4 v1.16 대응. 원본은 px4_controller/ 의 소스 대조 검증본(2026-07-07 재검증,
불일치 0건)을 파이썬으로 옮긴 것이다:

  QuadPlant           <- mc/quad_plant_params.m + benchmarks/p40_realtime.py (6-DoF 승격)
  PID                 <- 교육용 범용 이산 PID
  RateController      <- mc/px4_controller_step.m rate_control (rate_control.cpp)
  AttitudeController  <- mc/px4_controller_step.m attitude_control (AttitudeControl.cpp,
                         Brescianini 축소자세 + dyaw 재결합)
  PositionController  <- ctrl/ctrl_mc_px4.m 캐스케이드 + mc/px4_accel_to_att.m
                         (PositionControl::_accelerationControl + ControlMath)
  QuadXMixer          <- mc/px4_params.m quad-X 믹서 (control_allocator 의사역행렬
                         + 정규화 결과 상수)

규약(px4_controller 와 동일): NED z아래, 동체 FRD, 쿼터니언 [w x y z] body->NED.
신호는 loopsym 규약대로 포트당 스칼라 — 벡터량은 연속 포트로 펼친다.
"""

import math

from .core import Block

_G = 9.80665            # CONSTANTS_ONE_G


# ----------------------------------------------------------------------
# 쿼터니언 유틸 (matrix 라이브러리 규약, q = [w x y z], 리스트)
# ----------------------------------------------------------------------
def _qmult(a, b):
    return [a[0]*b[0] - a[1]*b[1] - a[2]*b[2] - a[3]*b[3],
            a[0]*b[1] + a[1]*b[0] + a[2]*b[3] - a[3]*b[2],
            a[0]*b[2] - a[1]*b[3] + a[2]*b[0] + a[3]*b[1],
            a[0]*b[3] + a[1]*b[2] - a[2]*b[1] + a[3]*b[0]]


def _qinv(q):
    return [q[0], -q[1], -q[2], -q[3]]


def _qnorm(q):
    n = math.sqrt(sum(c * c for c in q)) or 1e-9
    return [c / n for c in q]


def _dcm_z(q):
    """회전행렬의 3번째 열 (body z 축의 world 표현)."""
    a, b, c, d = q
    return [2.0 * (b*d + a*c), 2.0 * (c*d - a*b), a*a - b*b - c*c + d*d]


def _q_canonical(q):
    s = 1.0
    for c in q[:3]:
        if c > 1e-9:
            s = 1.0
            break
        if c < -1e-9:
            s = -1.0
            break
    else:
        if q[3] < 0.0:
            s = -1.0
    return [s * c for c in q]


def _q_from_two_vectors(src, dst):
    cr = [src[1]*dst[2] - src[2]*dst[1],
          src[2]*dst[0] - src[0]*dst[2],
          src[0]*dst[1] - src[1]*dst[0]]
    d = sum(s * t for s, t in zip(src, dst))
    if math.sqrt(sum(c * c for c in cr)) < 1e-5 and d < 0:
        a = [abs(c) for c in src]
        if a[0] <= a[1] and a[0] <= a[2]:
            e = [1.0, 0.0, 0.0]
        elif a[1] <= a[2]:
            e = [0.0, 1.0, 0.0]
        else:
            e = [0.0, 0.0, 1.0]
        v = [src[1]*e[2] - src[2]*e[1],
             src[2]*e[0] - src[0]*e[2],
             src[0]*e[1] - src[1]*e[0]]
        n = math.sqrt(sum(c * c for c in v))
        return [0.0, v[0]/n, v[1]/n, v[2]/n]
    return _qnorm([d + 1.0, cr[0], cr[1], cr[2]])


def _eul2quat(roll, pitch, yaw):
    """ZYX(3-2-1) 오일러 -> [w x y z]."""
    cr, sr = math.cos(roll/2), math.sin(roll/2)
    cp, sp = math.cos(pitch/2), math.sin(pitch/2)
    cy, sy = math.cos(yaw/2), math.sin(yaw/2)
    return [cr*cp*cy + sr*sp*sy, sr*cp*cy - cr*sp*sy,
            cr*sp*cy + sr*cp*sy, cr*cp*sy - sr*sp*cy]


def _quat2eul(q):
    """[w x y z] -> [roll pitch yaw] (ZYX)."""
    a, b, c, d = q
    sinp = min(max(2*(a*c - d*b), -1.0), 1.0)
    return [math.atan2(2*(a*b + c*d), 1 - 2*(b*b + c*c)),
            math.asin(sinp),
            math.atan2(2*(a*d + b*c), 1 - 2*(c*c + d*d))]


def _alpha_filter(state, sample, dt, cutoff):
    """PX4 AlphaFilter (cutoff<=0 이면 통과)."""
    if cutoff <= 0:
        return sample
    tc = 1.0 / (2.0 * math.pi * cutoff)
    a = dt / (dt + tc)
    return state + a * (sample - state)


def _clip(v, lo, hi):
    return min(max(v, lo), hi)


# ----------------------------------------------------------------------
# Plant — 6-DoF 쿼드로터 (연속, RK4 로 적분됨)
# ----------------------------------------------------------------------
class QuadPlant(Block):
    """quad-X 6-DoF 플랜트. 입력 모터 4 [0..1] -> 상태 13.

    출력: [qw qx qy qz | p q r | pN pE pD | vN vE vD]  (0..12)
    파라미터 기본값 = mc/quad_plant_params.m (호버 = 모터 0.5).
    로터 배치/부호는 QuadXMixer 와 자기일관 (px4_compute_mixer 의 quad-X).
    """

    n_in = 4
    n_out = 13
    state_size = 13
    feedthrough = False

    # 모터 순서: 1 전우(+CCW) 2 후좌(+CCW) 3 전좌(-CW) 4 후우(-CW)
    _PX = (1.0, -1.0, 1.0, -1.0)
    _PY = (1.0, -1.0, -1.0, 1.0)
    _SPIN = (1.0, 1.0, -1.0, -1.0)

    def __init__(self, m=1.0, g=9.81, ixx=0.02, iyy=0.02, izz=0.04,
                 arm=0.25, c_m=0.06, roll0=0.0, pitch0=0.0, yaw0=0.0,
                 z0=0.0, name=None):
        super().__init__(name)
        self.m, self.g = m, g
        self.ixx, self.iyy, self.izz = ixx, iyy, izz
        self.inertia = (ixx, iyy, izz)
        self.arm, self.c_m = arm, c_m
        self.kF = m * g / 2.0                     # 호버 시 모터당 u=0.5
        self.roll0, self.pitch0, self.yaw0, self.z0 = roll0, pitch0, yaw0, z0

    def initial(self):
        q = _eul2quat(self.roll0, self.pitch0, self.yaw0)
        return tuple(q) + (0.0, 0.0, 0.0) + (0.0, 0.0, self.z0) + (0.0, 0.0, 0.0)

    def output(self, t, u, x):
        return x

    def derivative(self, t, u, x):
        q = list(x[0:4])
        w = x[4:7]
        vel = x[10:13]
        f = [self.kF * _clip(ui, 0.0, 1.0) for ui in u]      # 모터 추력 [N]
        thrust = sum(f)
        tau = [sum(-self.arm * py * fi for py, fi in zip(self._PY, f)),
               sum(self.arm * px * fi for px, fi in zip(self._PX, f)),
               sum(self.c_m * s * fi for s, fi in zip(self._SPIN, f))]

        qw, qx, qy, qz = q
        # R(q) 3번째 열에 body 추력 [0,0,-T/m] 을 곱한 것 = 추력의 NED 가속
        az_b = -thrust / self.m
        acc = [2*(qx*qz + qw*qy) * az_b,
               2*(qy*qz - qw*qx) * az_b,
               self.g + (qw*qw - qx*qx - qy*qy + qz*qz) * az_b]

        dq = [0.5 * (-qx*w[0] - qy*w[1] - qz*w[2]),
              0.5 * (qw*w[0] + qy*w[2] - qz*w[1]),
              0.5 * (qw*w[1] - qx*w[2] + qz*w[0]),
              0.5 * (qw*w[2] + qx*w[1] - qy*w[0])]
        # Baumgarte 정규화 보정 (p40_realtime 승격분)
        corr = 0.5 * (1.0 - sum(c * c for c in q))
        dq = [dqi + corr * qi for dqi, qi in zip(dq, q)]

        ii = self.inertia
        dw = [(tau[0] - (w[1]*ii[2]*w[2] - w[2]*ii[1]*w[1])) / ii[0],
              (tau[1] - (w[2]*ii[0]*w[0] - w[0]*ii[2]*w[2])) / ii[1],
              (tau[2] - (w[0]*ii[1]*w[1] - w[1]*ii[0]*w[0])) / ii[2]]

        return tuple(dq) + tuple(dw) + tuple(vel) + tuple(acc)


def _att_error_quat(q, qd, yaw_w):
    """AttitudeControl.cpp (Brescianini): 자세오차 eq = 2·vec(q⁻¹⊗qd_mixed).

    roll/pitch 를 우선하기 위해 yaw 를 무시한 축소 목표자세를 만들고,
    delta-yaw 성분을 yaw_w 로 스케일해 재결합한다."""
    q = _qnorm(q)
    e_z, e_z_d = _dcm_z(q), _dcm_z(qd)
    qd_red = _q_from_two_vectors(e_z, e_z_d)
    if abs(qd_red[1]) > 1 - 1e-5 or abs(qd_red[2]) > 1 - 1e-5:
        qd_red = qd                       # 추력 방향 정반대 특이점
    else:
        qd_red = _qmult(qd_red, q)

    qd_dyaw = _q_canonical(_qmult(_qinv(qd_red), qd))
    w0 = _clip(qd_dyaw[0], -1.0, 1.0)
    z0 = _clip(qd_dyaw[3], -1.0, 1.0)
    dyaw = [math.cos(yaw_w * math.acos(w0)), 0.0, 0.0,
            math.sin(yaw_w * math.asin(z0))]
    qd = _qmult(qd_red, dyaw)

    qe = _q_canonical(_qmult(_qinv(q), qd))
    return [2.0 * qe[1], 2.0 * qe[2], 2.0 * qe[3]]


# ----------------------------------------------------------------------
# Control
# ----------------------------------------------------------------------
class PID(Block):
    """교육용 이산 PID: y = kp·e + I − kd·(e−e_prev)/st.  입력 = 오차."""

    n_in = 1
    dstate_size = 2          # (적분, 이전 오차)

    def __init__(self, kp=1.0, ki=0.0, kd=0.0, st=0.01, lim=0.0, name=None):
        super().__init__(name)
        self.kp, self.ki, self.kd = kp, ki, kd
        self.st = self.sample_time = st
        self.lim = lim       # 출력 포화 (0 = 없음)

    def output(self, t, u, xd):
        e = u[0]
        y = self.kp * e + xd[0] + self.kd * (e - xd[1]) / self.st
        if self.lim > 0:
            y = _clip(y, -self.lim, self.lim)
        return (y,)

    def update(self, t, u, xd):
        i = xd[0] + self.ki * u[0] * self.st
        if self.lim > 0:
            i = _clip(i, -self.lim, self.lim)
        return (i, u[0])


class AttitudeController(Block):
    """PX4 자세 P (AttitudeControl.cpp, Brescianini). 무상태.

    입력: q(4) [0..3], att_cmd 오일러 roll/pitch/yaw [4..6]
    출력: rate_sp p/q/r (rad/s)
    """

    n_in = 7
    n_out = 3

    def __init__(self, roll_p=6.5, pitch_p=6.5, yaw_p=2.8, yaw_w=0.4, name=None):
        super().__init__(name)
        self.roll_p, self.pitch_p, self.yaw_p = roll_p, pitch_p, yaw_p
        self.att_p = (roll_p, pitch_p, yaw_p / yaw_w)      # setProportionalGain
        self.yaw_w = yaw_w
        self.rate_limit = tuple(r * math.pi / 180.0 for r in (220.0, 220.0, 200.0))

    def output(self, t, u, x):
        eq = _att_error_quat(list(u[0:4]), _eul2quat(u[4], u[5], u[6]), self.yaw_w)
        rate_sp = [eq[i] * self.att_p[i] for i in range(3)]
        return tuple(_clip(r, -L, L) for r, L in zip(rate_sp, self.rate_limit))


class RateController(Block):
    """PX4 각속도 PID (rate_control.cpp) + yaw 토크 LPF + 각가속 필터링 미분.

    입력: rate_sp p/q/r [0..2], rate p/q/r [3..5]
    출력: 정규화 토크 tx/ty/tz [-1..1] (포화는 믹서/플랜트에서)
    이산상태(10): rate_int(3), omega_prev(3), angacc_state(3), yaw_tq_state(1)
    """

    n_in = 6
    n_out = 3
    dstate_size = 10

    def __init__(self, st=0.004, name=None):
        super().__init__(name)
        self.st = self.sample_time = st
        # MC_*RATE_* v1.16 기본값 (px4_params.m)
        self.rate_p = (0.15, 0.15, 0.20)
        self.rate_i = (0.20, 0.20, 0.10)
        self.rate_d = (0.003, 0.003, 0.0)
        self.rate_ff = (0.0, 0.0, 0.0)
        self.int_lim = (0.30, 0.30, 0.30)
        self.yaw_tq_cutoff = 2.0             # MC_YAW_TQ_CUTOFF [Hz]
        self.angacc_cutoff = 30.0            # 각가속 추정 LPF [Hz] (시뮬 전용)

    def _step(self, u, xd):
        """(torque(3), xd 다음값) — 순수함수라 output/update 양쪽에서 호출."""
        dt = self.st
        rate_sp, rate = u[0:3], u[3:6]
        rate_int = list(xd[0:3])
        omega_prev = xd[3:6]
        angacc_state = list(xd[6:9])
        yaw_tq_state = xd[9]

        # 각가속도 추정 (필터링 미분) — MATLAB 판과 동일하게 '이번 스텝에 갱신 후 사용'
        angacc = [_alpha_filter(s, (w - wp) / dt, dt, self.angacc_cutoff)
                  for s, w, wp in zip(angacc_state, rate, omega_prev)]

        err = [sp - w for sp, w in zip(rate_sp, rate)]
        torque = [self.rate_p[i] * err[i] + rate_int[i]
                  - self.rate_d[i] * angacc[i] + self.rate_ff[i] * rate_sp[i]
                  for i in range(3)]

        # 적분 anti-windup: 큰 오차(400°/s)에서 I 감쇠
        for i in range(3):
            ifac = err[i] / (400.0 * math.pi / 180.0)
            ifac = max(0.0, 1.0 - ifac * ifac)
            ri = rate_int[i] + ifac * self.rate_i[i] * err[i] * dt
            if math.isfinite(ri):
                rate_int[i] = _clip(ri, -self.int_lim[i], self.int_lim[i])

        # yaw 토크 저역통과
        yaw_tq = _alpha_filter(yaw_tq_state, torque[2], dt, self.yaw_tq_cutoff)
        torque[2] = yaw_tq

        return torque, tuple(rate_int) + tuple(rate) + tuple(angacc) + (yaw_tq,)

    def output(self, t, u, xd):
        return tuple(self._step(u, xd)[0])

    def update(self, t, u, xd):
        return self._step(u, xd)[1]


class PositionController(Block):
    """PX4 위치 캐스케이드 (ctrl_mc_px4.m): 위치P → 속도PI → 가속도 →
    _accelerationControl + thrustToAttitude (실소스 포팅) → 자세cmd + 추력.

    입력: pos_sp N/E/D [0..2], yaw_sp [3], pos N/E/D [4..6], vel N/E/D [7..9]
    출력: att_cmd roll/pitch/yaw [0..2], thrust_cmd [3] (위 방향 양수 [0..1])
    이산상태(3): xy_int(2), z_int(1)
    """

    n_in = 10
    n_out = 4
    dstate_size = 3

    # MPC_* v1.16 기본값 (ctrl_mc_px4.m / px4_alt_params.m)
    XY_P, XY_VEL_MAX = 0.95, 12.0
    XY_VEL_P, XY_VEL_I, INT_LIM = 1.8, 0.4, 4.0
    Z_P, VZ_P, VZ_I = 1.0, 4.0, 2.0
    VZ_MAX_UP, VZ_MAX_DN = 3.0, 1.5
    THR_HOVER, THR_MIN, TILT_MAX = 0.5, 0.12, 45.0 * math.pi / 180.0

    def __init__(self, st=0.004, name=None):
        super().__init__(name)
        self.st = self.sample_time = st

    def _cascade(self, u, xd):
        """가속도 setpoint 계산 — output/update 공용."""
        pos_sp, yaw_sp, pos, vel = u[0:3], u[3], u[4:7], u[7:10]
        # XY: 위치 P -> 속도 sp (한계) -> 속도 PI -> 수평가속
        vx, vy = ((pos_sp[i] - pos[i]) * self.XY_P for i in range(2))
        spd = math.hypot(vx, vy)
        if spd > self.XY_VEL_MAX:
            vx, vy = vx * self.XY_VEL_MAX / spd, vy * self.XY_VEL_MAX / spd
        exy = (vx - vel[0], vy - vel[1])
        acc_xy = [e * self.XY_VEL_P + i for e, i in zip(exy, xd[0:2])]
        # Z: 위치 P -> 승강속도 sp -> 속도 PI -> 수직가속
        vz_sp = _clip((pos_sp[2] - pos[2]) * self.Z_P, -self.VZ_MAX_UP, self.VZ_MAX_DN)
        ez = vz_sp - vel[2]
        acc_z = ez * self.VZ_P + xd[2]
        return (acc_xy[0], acc_xy[1], acc_z), (exy[0], exy[1], ez), yaw_sp

    def output(self, t, u, xd):
        acc, _, yaw_sp = self._cascade(u, xd)
        return _accel_to_att(acc, yaw_sp)

    def update(self, t, u, xd):
        _, err, _ = self._cascade(u, xd)
        dt = self.st
        return (_clip(xd[0] + err[0] * self.XY_VEL_I * dt, -self.INT_LIM, self.INT_LIM),
                _clip(xd[1] + err[1] * self.XY_VEL_I * dt, -self.INT_LIM, self.INT_LIM),
                _clip(xd[2] + err[2] * self.VZ_I * dt, -self.INT_LIM, self.INT_LIM))


def _accel_to_att(acc, yaw_sp, hover=0.5, thr_min=0.12,
                  tilt_max=45.0 * math.pi / 180.0):
    """가속도 setpoint -> (roll, pitch, yaw, thrust).  PX4 실소스 대응:
    PositionControl::_accelerationControl + ControlMath::thrustToAttitude."""
    bz = [-acc[0], -acc[1], _G]                   # 수직은 상수 표준중력 (디커플링)
    n = math.sqrt(sum(c * c for c in bz))
    bz = [c / n for c in bz]
    # limitTilt(bz, [0,0,1], tilt_max)
    dp = _clip(bz[2], -1.0, 1.0)
    ang = min(math.acos(dp), tilt_max)
    rej = [bz[0], bz[1], bz[2] - dp]
    rn = math.sqrt(sum(c * c for c in rej))
    rej = [1.0, 0.0, 0.0] if rn * rn < 1e-12 else [c / rn for c in rej]
    bz = [math.cos(ang) * w + math.sin(ang) * r
          for w, r in zip((0.0, 0.0, 1.0), rej)]

    coll = acc[2] * (hover / _G) - hover
    coll = coll / bz[2]                           # 계획 자세로 추력 투영
    coll = min(coll, -thr_min)                    # 음수(위), 최소추력 보장
    thr_sp = [c * coll for c in bz]

    q_sp = _bodyz_to_attitude([-c for c in thr_sp], yaw_sp)
    eul = _quat2eul(q_sp)
    return (eul[0], eul[1], eul[2], math.sqrt(sum(c * c for c in thr_sp)))


def _bodyz_to_attitude(body_z, yaw_sp):
    """ControlMath::bodyzToAttitude — body_z + yaw -> q (body->NED)."""
    if sum(c * c for c in body_z) < 1e-12:
        body_z = [0.0, 0.0, 1.0]
    n = math.sqrt(sum(c * c for c in body_z))
    bz = [c / n for c in body_z]
    y_c = [-math.sin(yaw_sp), math.cos(yaw_sp), 0.0]
    bx = [y_c[1]*bz[2] - y_c[2]*bz[1],
          y_c[2]*bz[0] - y_c[0]*bz[2],
          y_c[0]*bz[1] - y_c[1]*bz[0]]
    if bz[2] < 0:
        bx = [-c for c in bx]
    if abs(bz[2]) < 1e-6:
        bx = [0.0, 0.0, 1.0]
    n = math.sqrt(sum(c * c for c in bx))
    bx = [c / n for c in bx]
    by = [bz[1]*bx[2] - bz[2]*bx[1],
          bz[2]*bx[0] - bz[0]*bx[2],
          bz[0]*bx[1] - bz[1]*bx[0]]
    # R 열 = [bx by bz] (body->NED) -> 쿼터니언 (trace 4-분기)
    R = [[bx[0], by[0], bz[0]], [bx[1], by[1], bz[1]], [bx[2], by[2], bz[2]]]
    tr = R[0][0] + R[1][1] + R[2][2]
    if tr > 0:
        s = math.sqrt(1 + tr)
        q = [0.5 * s, 0.0, 0.0, 0.0]
        s = 0.5 / s
        q[1] = (R[2][1] - R[1][2]) * s
        q[2] = (R[0][2] - R[2][0]) * s
        q[3] = (R[1][0] - R[0][1]) * s
    elif R[0][0] > R[1][1] and R[0][0] > R[2][2]:
        s = math.sqrt(1 + R[0][0] - R[1][1] - R[2][2])
        q = [0.0, 0.5 * s, 0.0, 0.0]
        s = 0.5 / s
        q[0] = (R[2][1] - R[1][2]) * s
        q[2] = (R[1][0] + R[0][1]) * s
        q[3] = (R[0][2] + R[2][0]) * s
    elif R[1][1] > R[2][2]:
        s = math.sqrt(1 - R[0][0] + R[1][1] - R[2][2])
        q = [0.0, 0.0, 0.5 * s, 0.0]
        s = 0.5 / s
        q[0] = (R[0][2] - R[2][0]) * s
        q[1] = (R[1][0] + R[0][1]) * s
        q[3] = (R[2][1] + R[1][2]) * s
    else:
        s = math.sqrt(1 - R[0][0] - R[1][1] + R[2][2])
        q = [0.0, 0.0, 0.0, 0.5 * s]
        s = 0.5 / s
        q[0] = (R[1][0] - R[0][1]) * s
        q[1] = (R[0][2] + R[2][0]) * s
        q[2] = (R[2][1] + R[1][2]) * s
    return _qnorm(q)


# ----------------------------------------------------------------------
# 화이트박스 조립용 소형 블록 — Simulink 블록판의 MATLAB Function 상당.
# 캐스케이드/PID/필터는 기본 블록(Gain/Sum/Saturation/UnitDelay)으로 그리고,
# 쿼터니언 좌표변환만 이 블록들을 쓴다 (examples/ex9 참조).
# ----------------------------------------------------------------------
class EulerToQuat(Block):
    """att_cmd 오일러(ZYX) -> q_sp [w x y z].  (mc/px4_eul2quat.m)"""

    n_in = 3
    n_out = 4

    def output(self, t, u, x):
        return tuple(_eul2quat(u[0], u[1], u[2]))


class QuatAttitudeError(Block):
    """q(4)+q_sp(4) -> 자세오차 eq(3) (Brescianini, yaw_w 재결합 포함).

    각속도 setpoint 는 바깥에서 eq × att_p Gain + Saturation 으로 만든다.
    (mc/px4_att_error.m 상당)"""

    n_in = 8
    n_out = 3

    def __init__(self, yaw_w=0.4, name=None):
        super().__init__(name)
        self.yaw_w = yaw_w

    def output(self, t, u, x):
        return tuple(_att_error_quat(list(u[0:4]), _qnorm(list(u[4:8])), self.yaw_w))


class AccelToAttitude(Block):
    """acc_sp(3)+yaw_sp -> att_cmd 오일러(3)+thrust.  (mc/px4_accel_to_att.m)"""

    n_in = 4
    n_out = 4

    def __init__(self, hover=0.5, thr_min=0.12, name=None):
        super().__init__(name)
        self.hover, self.thr_min = hover, thr_min

    def output(self, t, u, x):
        return _accel_to_att(u[0:3], u[3], self.hover, self.thr_min)


# ----------------------------------------------------------------------
# Allocation
# ----------------------------------------------------------------------
class QuadXMixer(Block):
    """PX4 제어할당 quad-X (4001_quad_x) — control_allocator 의사역행렬+정규화 상수.

    입력: 토크 tx/ty/tz [0..2], collective 추력 [3] (위 방향 양수 [0..1])
    출력: 모터 m1..m4 [0..1]
    """

    n_in = 4
    n_out = 4

    _MIXER = ((-0.707107, 0.707107, 1.0, -1.0),
              (0.707107, -0.707107, 1.0, -1.0),
              (0.707107, 0.707107, -1.0, -1.0),
              (-0.707107, -0.707107, -1.0, -1.0))   # 열: Mx My Mz Tz

    def output(self, t, u, x):
        ctrl = (u[0], u[1], u[2], -u[3])            # thrust_sp_z = -thrust (z아래 +)
        return tuple(_clip(sum(m * c for m, c in zip(row, ctrl)), 0.0, 1.0)
                     for row in self._MIXER)
