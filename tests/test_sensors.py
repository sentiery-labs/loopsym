"""센서 규약 + IMU (CLD-P62) — ARCHITECTURE §2 fidelity 규약 검증."""

import math

import pytest

from loopsym import (
    Constant, Diagram, IMU, Scope, Simulator, Step,
    QuadPlant, RateController, AttitudeController, QuadXMixer,
)

DT = 0.004
DEG = math.pi / 180.0


def _build_hover(fidelity, seed=0, gyro_nd=5e-5):
    """호버 폐루프 — rate 피드백이 IMU gyro 를 경유 (다이어그램은 하나,
    fidelity 만 다르다)."""
    bd = Diagram()
    plant = bd.add(QuadPlant(roll0=10 * DEG, pitch0=-5 * DEG, z0=-5.0))
    imu = bd.add(IMU(fidelity=fidelity, seed=seed, gyro_nd=gyro_nd, st=DT))
    att = bd.add(AttitudeController())
    rate = bd.add(RateController(st=DT))
    mix = bd.add(QuadXMixer())
    zero = bd.add(Constant(0.0))
    thr = bd.add(Constant(0.5))
    for i in range(4):
        bd.connect(plant[i], imu[i])            # q
        bd.connect(plant[i], att[i])
    for i in range(3):
        bd.connect(plant[4 + i], imu[4 + i])    # omega
        bd.connect(plant[10 + i], imu[7 + i])   # vel
        bd.connect(zero, att[4 + i])            # att_cmd = level
        bd.connect(att[i], rate[i])
        bd.connect(imu[i], rate[3 + i])         # rate 피드백 = IMU gyro ★
        bd.connect(rate[i], mix[i])
    bd.connect(thr, mix[3])
    for i in range(4):
        bd.connect(mix[i], plant[i])
    sc = bd.add(Scope(n_in=2, labels=["qx", "gyro_p"]))
    bd.connect(plant[1], sc[0])
    bd.connect(imu[0], sc[1])
    return bd, sc


def test_port_signature_invariant_across_fidelity():
    """§2 핵심: fidelity 가 바뀌어도 포트 수/의미 불변."""
    for f in ("ideal", "noisy"):
        b = IMU(fidelity=f)
        assert (b.n_in, b.n_out) == (10, 6)
    with pytest.raises(NotImplementedError):
        IMU(fidelity="world")                   # IMU 는 Level 2 미지원
    with pytest.raises(NotImplementedError):
        IMU(fidelity="hardware")                # 예약 (P41/P43)
    with pytest.raises(ValueError):
        IMU(fidelity="oops")


def test_ideal_is_passthrough():
    """ideal: gyro = 참 각속도, 레벨 정지에서 비력 = [0,0,-g]."""
    imu = IMU(fidelity="ideal", st=DT)
    u = (1, 0, 0, 0, 0.1, -0.2, 0.3, 0, 0, 0)   # 레벨, omega=(.1,-.2,.3), vel=0
    xd = (0.0,) * 9
    y = imu.output(0, u, xd)
    assert y[0:3] == (0.1, -0.2, 0.3)
    assert y[3] == pytest.approx(0) and y[4] == pytest.approx(0)
    assert y[5] == pytest.approx(-9.81)


def test_noisy_seed_reproducible():
    """같은 seed → 비트 동일 (채점/회귀), 다른 seed → 다른 잡음."""
    def run(seed):
        bd, sc = _build_hover("noisy", seed=seed)
        Simulator(bd).run(1.0, DT)
        return sc.data[1]
    a, b, c = run(7), run(7), run(8)
    assert a == b
    assert a != c


def test_noisy_degrades_attitude_hold():
    """§4 T2 데모 판정: ideal↔noisy 전환 → 자세(qx) 유지 성능 열화.

    잡음밀도는 datasheet 급보다 크게(수업 가시성) — 정착 후 qx 흔들림 비교.
    """
    bd_i, sc_i = _build_hover("ideal")
    bd_n, sc_n = _build_hover("noisy", gyro_nd=5e-3)
    Simulator(bd_i).run(4.0, DT)
    Simulator(bd_n).run(4.0, DT)
    tail = len(sc_i.data[0]) // 2               # 정착 후 절반 구간
    rms = lambda ch: math.sqrt(sum(v * v for v in ch[tail:]) / len(ch[tail:]))
    rms_i, rms_n = rms(sc_i.data[0]), rms(sc_n.data[0])
    assert rms_i < 1e-4                          # ideal: 사실상 완전 정지
    assert rms_n > 5 * rms_i                     # noisy: 뚜렷한 열화
    assert rms_n < 0.05                          # 그래도 발산은 안 함 (제어기가 버팀)


def test_imu_json_roundtrip():
    import json
    from loopsym.viz import export_json
    from loopsym.webapi import run_simulation
    bd, _ = _build_hover("noisy", seed=3)
    out = json.loads(run_simulation(json.dumps(export_json(bd)), 0.5, DT))
    assert out["errors"] == []


def test_world_fidelity_not_supported_by_imu():
    """Level 2 "world"(3D 월드 연동)는 IMU 가 아직 지원하지 않는다."""
    with pytest.raises(NotImplementedError, match="world"):
        IMU(fidelity="world")


def test_gazebo_fidelity_name_removed():
    """2026-11-27 개정: Level 2 이름 gazebo → world. 옛 이름은 잘못된 값."""
    with pytest.raises(ValueError):
        IMU(fidelity="gazebo")


def test_fidelity_names():
    from loopsym.sensors import _FIDELITY
    assert _FIDELITY == ("ideal", "noisy", "world", "hardware")
