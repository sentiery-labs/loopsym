"""드론 팔레트(CLD-P65) 검증 — px4_controller Simulink 검증본과 같은 판정 기준.

호버 테스트  = mc/run_px4_hover_test  (roll 10°, pitch −5° 기울여 시작 → 레벨 복귀)
위치 테스트  = mc/run_px4_pos_test_blocks (북 2m + 고도 6m 이동 후 정지 호버)
"""

import math

import pytest

from loopsym import (
    Constant, Diagram, PID, Scope, Simulator, Step,
    Mixer, QuadPlant, RateController, AttitudeController, PositionController,
    QuadXMixer,
)
from loopsym.viz import export_json, load_json
from loopsym.webapi import run_simulation

DT = 0.004
DEG = math.pi / 180.0


def _wire_att_chain(bd, plant, att_cmd_blocks, thrust_block):
    """자세+각속도+믹서 폐루프 공통 배선. att_cmd_blocks = (roll, pitch, yaw) 소스."""
    att = bd.add(AttitudeController())
    rate = bd.add(RateController(st=DT))
    mix = bd.add(QuadXMixer())
    for i in range(4):                       # q -> att
        bd.connect(plant[i], att[i])
    for i, src in enumerate(att_cmd_blocks):  # att_cmd
        bd.connect(src, att[4 + i])
    for i in range(3):                       # rate_sp, rate
        bd.connect(att[i], rate[i])
        bd.connect(plant[4 + i], rate[3 + i])
    for i in range(3):                       # torque -> mixer
        bd.connect(rate[i], mix[i])
    bd.connect(thrust_block, mix[3])
    for i in range(4):                       # motors -> plant
        bd.connect(mix[i], plant[i])
    return att, rate, mix


def test_mixer_hover_and_signs():
    mix = QuadXMixer()
    # 순수 호버: 토크 0, 추력 0.5 -> 모든 모터 0.5
    assert mix.output(0, (0, 0, 0, 0.5), ()) == (0.5, 0.5, 0.5, 0.5)
    # +roll 토크 -> 모터 [감소, 증가, 증가, 감소] (전우-, 후좌+, 전좌+, 후우-)
    m = mix.output(0, (0.1, 0, 0, 0.5), ())
    assert m[0] < 0.5 < m[1] and m[2] > 0.5 > m[3]
    # +yaw 토크 -> CCW 모터(1,2) 증가, CW 모터(3,4) 감소
    m = mix.output(0, (0, 0, 0.1, 0.5), ())
    assert m[0] > 0.5 and m[1] > 0.5 and m[2] < 0.5 and m[3] < 0.5


def test_attitude_controller_direction():
    att = AttitudeController()
    level = (1.0, 0.0, 0.0, 0.0)
    # 레벨에서 +roll 명령 -> +p 방향 rate_sp, 소각에서 rate_sp ≈ att_p * 오차
    rate_sp = att.output(0, level + (10 * DEG, 0.0, 0.0), ())
    assert abs(rate_sp[0] - 6.5 * 10 * DEG) < 0.01 and rate_sp[0] > 0
    assert abs(rate_sp[1]) < 1e-9 and abs(rate_sp[2]) < 1e-9
    # yaw 명령은 yaw_w 재결합을 거쳐도 +r 방향
    rate_sp = att.output(0, level + (0.0, 0.0, 30 * DEG), ())
    assert rate_sp[2] > 0


def test_hover_attitude_recovery():
    """검증본 run_px4_hover_test 재현: 기울여 시작 -> 레벨 복귀, 발산 없음."""
    bd = Diagram()
    plant = bd.add(QuadPlant(roll0=10 * DEG, pitch0=-5 * DEG, z0=-5.0))
    zero = bd.add(Constant(0.0))
    thr = bd.add(Constant(0.5))
    _wire_att_chain(bd, plant, (zero, zero, zero), thr)
    sc = bd.add(Scope(n_in=4, labels=["qw", "qx", "qy", "qz"]))
    for i in range(4):
        bd.connect(plant[i], sc[i])

    sim = Simulator(bd)
    sim.run(4.0, DT)
    qw, qx, qy, qz = (ch[-1] for ch in sc.data)
    roll = math.atan2(2 * (qw * qx + qy * qz), 1 - 2 * (qx * qx + qy * qy))
    pitch = math.asin(max(-1, min(1, 2 * (qw * qy - qz * qx))))
    assert all(math.isfinite(v) for ch in sc.data for v in ch)      # 발산 없음
    assert abs(roll) < 0.5 * DEG and abs(pitch) < 0.5 * DEG          # 레벨 복귀
    assert abs(qw) > 0.9999                                          # 자세 정착


def test_position_move_north_and_climb():
    """검증본 run_px4_pos_test_blocks 재현: 북 2m + 고도 6m -> 정지 호버."""
    bd = Diagram()
    plant = bd.add(QuadPlant(z0=-5.0))
    pos = bd.add(PositionController(st=DT))
    zero = bd.add(Constant(0.0))
    n_sp = bd.add(Step(t_on=0.5, height=2.0))       # 북 2m
    d_sp = bd.add(Constant(-6.0))                   # 고도 6m (NED z=-6)
    bd.connect(n_sp, pos[0])
    bd.connect(zero, pos[1])
    bd.connect(d_sp, pos[2])
    bd.connect(zero, pos[3])                        # yaw_sp
    for i in range(3):                              # pos, vel 피드백
        bd.connect(plant[7 + i], pos[4 + i])
        bd.connect(plant[10 + i], pos[7 + i])

    att = bd.add(AttitudeController())
    rate = bd.add(RateController(st=DT))
    mix = bd.add(QuadXMixer())
    for i in range(4):
        bd.connect(plant[i], att[i])
    for i in range(3):
        bd.connect(pos[i], att[4 + i])              # att_cmd = 위치제어 출력
        bd.connect(att[i], rate[i])
        bd.connect(plant[4 + i], rate[3 + i])
        bd.connect(rate[i], mix[i])
    bd.connect(pos[3], mix[3])                      # thrust_cmd
    for i in range(4):
        bd.connect(mix[i], plant[i])

    sc = bd.add(Scope(n_in=3, labels=["N", "E", "D"]))
    for i in range(3):
        bd.connect(plant[7 + i], sc[i])

    Simulator(bd).run(8.0, DT)
    n, e, d = (ch[-1] for ch in sc.data)
    assert abs(n - 2.0) < 0.1 and abs(e) < 0.1 and abs(d + 6.0) < 0.1
    # 정착(마지막 0.5s 동안 이동 < 2cm)
    assert abs(sc.data[0][-1] - sc.data[0][-125]) < 0.02


@pytest.mark.parametrize("frame", ["quad_x", "quad_plus", "hexa_x", "octo_x"])
def test_frame_hover_recovery(frame):
    """프레임별 플랜트+믹서 자기일관: 어느 기체든 같은 제어기로 레벨 복귀.

    제어기는 정규화 wrench 만 내고 기체 차이는 Mixer 가 흡수 (PX4 구조).
    """
    bd = Diagram()
    plant = bd.add(QuadPlant(frame=frame, roll0=10 * DEG, pitch0=-5 * DEG, z0=-5.0))
    att = bd.add(AttitudeController())
    rate = bd.add(RateController(st=DT))
    mix = bd.add(Mixer(frame=frame))
    zero = bd.add(Constant(0.0))
    thr = bd.add(Constant(0.5))
    n = plant.n_in
    assert mix.n_out == n
    for i in range(4):
        bd.connect(plant[i], att[i])
    for i in range(3):
        bd.connect(zero, att[4 + i])
        bd.connect(att[i], rate[i])
        bd.connect(plant[4 + i], rate[3 + i])
        bd.connect(rate[i], mix[i])
    bd.connect(thr, mix[3])
    for i in range(n):
        bd.connect(mix[i], plant[i])
    sc = bd.add(Scope(n_in=3, labels=["qw", "qx", "qy"]))
    for i in range(3):
        bd.connect(plant[i], sc[i])
    Simulator(bd).run(4.0, DT)
    qw, qx, qy = (ch[-1] for ch in sc.data)
    assert all(math.isfinite(v) for ch in sc.data for v in ch)
    assert abs(qx) < 0.005 and abs(qy) < 0.005 and qw > 0.9999   # 레벨 복귀


def test_pid_block_step_tracking():
    """범용 PID: 1차 플랜트 폐루프 스텝 추종."""
    from loopsym import Integrator, Sum
    bd = Diagram()
    ref = bd.add(Step(t_on=0.0, height=1.0))
    err = bd.add(Sum("+-"))
    pid = bd.add(PID(kp=2.0, ki=1.0, st=0.01))
    plant = bd.add(Integrator())
    sc = bd.add(Scope(n_in=1))
    bd.connect(ref, err[0])
    bd.connect(plant, err[1])
    bd.connect(err, pid)
    bd.connect(pid, plant)
    bd.connect(plant, sc[0])
    # C(s)=2+1/s, P(s)=1/s -> (s+1)^2 임계감쇠: 10s 후 잔차 ~(1+10)e^-10
    Simulator(bd).run(10.0, 0.01)
    assert abs(sc.data[0][-1] - 1.0) < 0.005


def test_drone_blocks_json_roundtrip():
    """export -> load 라운드트립 후에도 같은 결과 (뷰어/Pyodide 경로 보증)."""
    import json
    bd = Diagram()
    plant = bd.add(QuadPlant(roll0=10 * DEG, z0=-5.0))
    zero = bd.add(Constant(0.0))
    thr = bd.add(Constant(0.5))
    _wire_att_chain(bd, plant, (zero, zero, zero), thr)
    sc = bd.add(Scope(n_in=1, labels=["qx"]))
    bd.connect(plant[1], sc[0])

    out = json.loads(run_simulation(json.dumps(export_json(bd)), 2.0, DT))
    assert out["errors"] == []
    qx_end = out["signals"][[k for k in out["signals"]][0]][0][-1]
    assert abs(qx_end) < 0.005                       # 복귀 중 (레벨 근접)
