"""MavlinkHil (CLD-P41) — SITL 없이 검증 가능한 부분.

전체 파이프라인 검증(실펌웨어 이륙)은 examples/ex11_px4_sitl.py —
PX4 빌드가 필요해 CI 밖에 둔다 (로컬 실측 2026-07-19: 링크 100%,
호버 2.51m, PASS).
"""

import math
import random

import pytest

from loopsym import QuadPlant, MavlinkHil
from loopsym.mavlink import _ALT0, _MAG_NED_GAUSS, synth_hil_sensor


def test_synth_sensor_level_hover():
    """레벨 정지: 비력=[0,0,-g], 지자기=NED 값 그대로, 표준대기 기압."""
    rng = random.Random(0)
    s = synth_hil_sensor((1, 0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
                         0.0, 0.004, 9.81, rng)
    assert abs(s["acc"][2] + 9.81) < 0.1 and abs(s["acc"][0]) < 0.1
    assert abs(s["mag"][0] - _MAG_NED_GAUSS[0]) < 0.01
    assert abs(s["pressure_alt"] - _ALT0) < 1e-9
    assert 1000 < s["abs_pressure"] < 1013.25          # 고도 50m 의 표준대기


def test_synth_sensor_has_noise():
    """★STALE 가드: 같은 상태라도 값이 완전히 일정하면 안 된다."""
    rng = random.Random(0)
    a = synth_hil_sensor((1, 0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), 0, 0.004, 9.81, rng)
    b = synth_hil_sensor((1, 0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), 0, 0.004, 9.81, rng)
    assert a["acc"] != b["acc"] and a["gyro"] != b["gyro"]


def test_synth_sensor_specific_force_rotation():
    """90° 롤 자세에서 중력 비력이 body y 축으로 온다."""
    q = (math.cos(math.pi / 4), math.sin(math.pi / 4), 0, 0)   # roll 90°
    s = synth_hil_sensor(q, (0, 0, 0), (0, 0, 0), (0, 0, 0), 0, 0.004, 9.81,
                         random.Random(0))
    assert abs(s["acc"][1] - (-9.81)) < 0.1 or abs(s["acc"][1] - 9.81) < 0.1
    assert abs(s["acc"][2]) < 0.1


def test_transport_serial_reserved():
    with pytest.raises(NotImplementedError):
        MavlinkHil(transport="serial:/dev/ttyACM0")


def test_ground_model_rest_and_release():
    """지면 모델: 추력<mg 면 정지, 초과하면 이륙 가속."""
    p = QuadPlant(ground=True, z0=0.0)
    x = p.initial()
    assert p.derivative(0, (0.3, 0.3, 0.3, 0.3), x) == (0.0,) * 13   # 지상 정지
    d = p.derivative(0, (0.8, 0.8, 0.8, 0.8), x)                     # 추력 초과
    assert d[12] < 0                                                  # vḊ < 0 = 상승
    # 공중(z<0)에서는 ground 여도 자유 동역학
    x_air = tuple(-5.0 if i == 9 else v for i, v in enumerate(x))
    assert p.derivative(0, (0.0,) * 4, x_air)[12] > 0                 # 낙하 가속
