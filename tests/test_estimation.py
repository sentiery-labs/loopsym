"""Estimation 팔레트 (CLD-P64) — Mahony 상보필터 검증.

검증 방식은 px4_controller 의 nav_compare 와 동일한 **관측자 모드** (제어는
참값, 추정기는 관전): 순수 자이로 적분(kp=ki=0)은 바이어스로 무한 드리프트
하지만 CF 는 중력 보정으로 유계 + 바이어스 수렴.

주의(교육 포인트, 폐루프에 CF 만 넣으면 안 되는 이유): 가속도계는 비력을
측정하므로 추력만 받는 쿼드는 기울면 수평가속하며 비력이 항상 body-z
= "레벨처럼 보임" → 가속 중 tilt 관측 불가. 제어 루프 안에서 자세추정을
쓰려면 GPS 속도 결합(EKF2 방식)이 필요하다 — px4_controller/nav 의
EKF2_gravity_notes 참조. CF 는 저기동/호버 관측용.
"""

import math

from loopsym import (
    ComplementaryFilter, Constant, Diagram, IMU, Scope, Simulator,
    QuadPlant, RateController, AttitudeController, QuadXMixer,
)

DT = 0.004
DEG = math.pi / 180.0
# Mahony 바이어스 동역학 s²+Kp·s+Ki=0 의 느린 극점 ≈ -0.053 → τ ≈ 19s.
# 판정 시각은 τ 의 수 배로 잡는다.


def test_static_bias_and_tilt_convergence():
    """정지 IMU + 자이로 바이어스 -> bhat 이 참 바이어스로, 자세는 레벨 유지."""
    cf = ComplementaryFilter(st=DT)
    bias = 0.02                                  # rad/s (roll 축)
    u = (bias, 0.0, 0.0, 0.0, 0.0, -9.81)        # 정지·레벨: gyro=bias, accel=[0,0,-g]
    xd = cf.dinitial()
    for _ in range(int(120.0 / DT)):             # τ≈19s 의 ~6배
        xd = cf.update(0, u, xd)
    y = cf.output(0, u, xd)
    q, omega = y[0:4], y[4:7]
    assert abs(xd[4] - bias) < 2e-3              # bhat -> 참 바이어스
    assert abs(omega[0]) < 2e-3                   # 보정 각속도 -> 0
    roll = math.atan2(2 * (q[0]*q[1] + q[2]*q[3]), 1 - 2 * (q[1]*q[1] + q[2]*q[2]))
    assert abs(roll) < 0.5 * DEG                  # 레벨 유지 (바이어스 적분 안 됨)


def test_cf_bounds_drift_vs_pure_integration():
    """관측자 모드: noisy+바이어스 IMU 를 CF vs 순수적분(kp=ki=0)이 나란히 추정."""
    bd = Diagram()
    plant = bd.add(QuadPlant(roll0=10 * DEG, z0=-5.0))
    imu = bd.add(IMU(fidelity="noisy", gyro_bias=0.05, gyro_nd=1e-3, st=DT))
    cf = bd.add(ComplementaryFilter(st=DT))
    gyro_only = bd.add(ComplementaryFilter(kp=0.0, ki=0.0, st=DT))
    att = bd.add(AttitudeController())
    rate = bd.add(RateController(st=DT))
    mix = bd.add(QuadXMixer())
    zero = bd.add(Constant(0.0))
    thr = bd.add(Constant(0.5))
    # 제어는 참값 (관측자 모드 — 기체는 안정적으로 레벨 호버)
    for i in range(4):
        bd.connect(plant[i], att[i])
        bd.connect(plant[i], imu[i])
    for i in range(3):
        bd.connect(plant[4 + i], imu[4 + i])
        bd.connect(plant[10 + i], imu[7 + i])
        bd.connect(zero, att[4 + i])
        bd.connect(att[i], rate[i])
        bd.connect(plant[4 + i], rate[3 + i])
        bd.connect(rate[i], mix[i])
    bd.connect(thr, mix[3])
    for i in range(4):
        bd.connect(mix[i], plant[i])
    # 두 추정기가 같은 IMU 를 관전
    for i in range(6):
        bd.connect(imu[i], cf[i])
        bd.connect(imu[i], gyro_only[i])
    sc = bd.add(Scope(n_in=3, labels=["qx_true", "qx_cf", "qx_gyro"]))
    bd.connect(plant[1], sc[0])
    bd.connect(cf[1], sc[1])
    bd.connect(gyro_only[1], sc[2])

    Simulator(bd).run(40.0, DT)
    qx_t, qx_cf, qx_g = (ch[-1] for ch in sc.data)
    err_cf, err_g = abs(qx_cf - qx_t), abs(qx_g - qx_t)
    assert err_g > 20 * DEG / 2                   # 순수적분: 바이어스로 대폭 드리프트
    assert err_cf < 1 * DEG / 2                   # CF: 유계 + 바이어스 수렴 (qx≈roll/2)
    assert all(math.isfinite(v) for ch in sc.data for v in ch)
