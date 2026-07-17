"""Navigation 팔레트 — WaypointManager (13주차 커리큘럼의 엔진 조각)."""

import math

import pytest

from loopsym import (
    Constant, Diagram, Scope, Simulator, WaypointManager,
    QuadPlant, PositionController, AttitudeController, RateController, Mixer,
)

DT = 0.004


def test_waypoint_parsing():
    wp = WaypointManager(waypoints="1,2,-3; 4,5,-6")
    assert wp._wps == [(1.0, 2.0, -3.0), (4.0, 5.0, -6.0)]
    with pytest.raises(ValueError):
        WaypointManager(waypoints="1,2")           # 3개씩이 아님
    with pytest.raises(ValueError):
        WaypointManager(waypoints="")


def test_switching_logic():
    wp = WaypointManager(waypoints="0,0,-5; 2,0,-5", radius=0.5, st=DT)
    xd = wp.dinitial()
    assert wp.output(0, (9, 9, 9), xd)[0:3] == (0.0, 0.0, -5.0)
    xd = wp.update(0, (0.1, 0, -5), xd)            # 1번 지점 반경 안 -> 전환
    assert xd[0] == 1.0
    assert wp.output(0, (0, 0, 0), xd)[0:3] == (2.0, 0.0, -5.0)
    xd = wp.update(0, (2, 0, -5), xd)              # 마지막 지점 도달 -> idx=2 유지
    assert xd[0] == 2.0
    assert wp.update(0, (0, 0, 0), xd) == xd       # 더 안 오름
    assert wp.output(0, (0, 0, 0), xd)[0:3] == (2.0, 0.0, -5.0)   # 마지막 유지


def test_closed_loop_mission():
    """웨이포인트 2개 순회 미션 — 전부 방문 + 마지막 지점 호버."""
    bd = Diagram()
    plant = bd.add(QuadPlant(z0=-5.0))
    pos = bd.add(PositionController(st=DT))
    att = bd.add(AttitudeController())
    rate = bd.add(RateController(st=DT))
    mix = bd.add(Mixer())
    wp = bd.add(WaypointManager(waypoints="2,0,-6; 0,0,-5", radius=0.5, st=DT))
    yaw = bd.add(Constant(0.0))
    for i in range(3):
        bd.connect(plant[7 + i], wp[i])
        bd.connect(wp[i], pos[i])
        bd.connect(plant[7 + i], pos[4 + i])
        bd.connect(plant[10 + i], pos[7 + i])
    bd.connect(yaw, pos[3])
    for i in range(4):
        bd.connect(plant[i], att[i])
    for i in range(3):
        bd.connect(pos[i], att[4 + i])
        bd.connect(att[i], rate[i])
        bd.connect(plant[4 + i], rate[3 + i])
        bd.connect(rate[i], mix[i])
    bd.connect(pos[3], mix[3])
    for i in range(4):
        bd.connect(mix[i], plant[i])
    sc = bd.add(Scope(n_in=4, labels=["N", "E", "D", "idx"]))
    for i in range(3):
        bd.connect(plant[7 + i], sc[i])
    bd.connect(wp[3], sc[3])

    Simulator(bd).run(12.0, DT)
    n, e, d, idx = (ch[-1] for ch in sc.data)
    assert idx == 2.0                              # 전부 방문
    assert abs(n) < 0.15 and abs(e) < 0.15 and abs(d + 5.0) < 0.15
    assert all(math.isfinite(v) for ch in sc.data for v in ch)
