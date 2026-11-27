"""예제 12 — SENTIERY 3D 월드 연동: 세종대 캠퍼스 위를 쿼드가 순회 비행.

loopsym 이 물리(QuadPlant)와 제어(PX4 v1.16 위치제어)를 계산하고, 3D 월드는
받은 자세 그대로 기체를 그리면서 그 자리의 거리계·카메라·충돌 값을 돌려준다
(fidelity "world", lockstep — docs/world_link_protocol.md).

    WaypointManager → PositionController → AttitudeController → RateController → QuadXMixer → QuadPlant
                                                                                                  │ 상태 13
                       Rangefinder(fidelity="world") ◀── WorldLink ◀──────────────────────────────┤ + 모터 4
                       Camera (영상 → ex12_frames/)  ◀──┘   (TCP 9431 ⇄ SENTIERY 3D 월드)

기본 경로(NED, 출발 패드 기준): 이륙 → 고도 60 m → 서쪽 300 m(광개토관 위, 옥상
54.6 m) → 북 300 m → 동 300 m → 패드 위 → 착륙. 300 × 300 m 정사각.
월드 센서 값은 한 샘플(0.04 s) 늦다.

먼저 SENTIERY 개발판을 `-sentiery-loopsym` 으로 켜거나 편집기에서 세종대 장면의
loopsym 기체를 고르세요. 그다음:

    python examples/ex12_sentiery_world.py
    python examples/ex12_sentiery_world.py --waypoints "0,0,-30; 0,-150,-30" --no-camera

끝나면 고도·거리·지면 높이 요약을 출력하고 ex12_diagram.html 을 만든다(파형이
심겨 있어 바로 보인다 — 브라우저에서 재실행은 안 되고, 로컬 서버 모드에서는 된다).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loopsym import (                               # noqa: E402
    Constant, Diagram, Gain, Scope, Simulator, render_html,
    QuadPlant, PositionController, AttitudeController, RateController, QuadXMixer,
    WaypointManager, WorldLink, Rangefinder, Camera, WorldCollision, WorldLinkError,
)
from loopsym.world_protocol import DEFAULT_PORT     # noqa: E402

DT = 0.004          # PX4 자세루프 250 Hz (ex7 과 같음)
LINK_ST = 0.04      # 3D 월드 연동 25 Hz
DEFAULT_WAYPOINTS = "0,0,-60; 0,-300,-60; 300,-300,-60; 300,0,-60; 0,0,-60; 0,0,-0.5"


def build(host="127.0.0.1", port=DEFAULT_PORT, waypoints=DEFAULT_WAYPOINTS, camera=True,
          save_dir="ex12_frames"):
    """다이어그램과 Scope 둘(위치 N/E/D, 고도·거리·지면 높이)을 돌려준다."""
    bd = Diagram()
    plant = bd.add(QuadPlant(ground=True, z0=0.0, name="quad"))
    wp = bd.add(WaypointManager(waypoints, radius=2.0, name="mission"))
    pos = bd.add(PositionController(st=DT, name="pos_ctrl"))
    att = bd.add(AttitudeController(name="att_ctrl"))
    rate = bd.add(RateController(st=DT, name="rate_ctrl"))
    mix = bd.add(QuadXMixer(name="mixer"))
    link = bd.add(WorldLink(host=host, port=port, st=LINK_ST, name="world"))
    rng = bd.add(Rangefinder(fidelity="world", st=LINK_ST, link="world", name="lidar"))

    # ---- 미션 → 위치제어 → 자세 → 각속도 → 믹서 → 플랜트 (ex7 과 같은 사슬) ----
    yaw_sp = bd.add(Constant(0.0, name="yaw_sp"))
    for i in range(3):
        bd.connect(plant[7 + i], wp[i])             # 현재 위치 → 웨이포인트 도달 판정
        bd.connect(wp[i], pos[i])                   # 위치 setpoint
        bd.connect(plant[7 + i], pos[4 + i])        # pos N/E/D
        bd.connect(plant[10 + i], pos[7 + i])       # vel N/E/D
    bd.connect(yaw_sp, pos[3])
    for i in range(4):
        bd.connect(plant[i], att[i])                # q
    for i in range(3):
        bd.connect(pos[i], att[4 + i])              # att_cmd
        bd.connect(att[i], rate[i])                 # rate_sp
        bd.connect(plant[4 + i], rate[3 + i])       # p q r
        bd.connect(rate[i], mix[i])                 # torque
    bd.connect(pos[3], mix[3])                      # thrust
    for i in range(4):
        bd.connect(mix[i], plant[i])                # motors

    # ---- 3D 월드: 상태 13 + 모터 4 → WorldLink, 같은 상태 → 센서 ----
    for i in range(13):
        bd.connect(plant[i], link[i])
        bd.connect(plant[i], rng[i])
    for i in range(4):
        bd.connect(mix[i], link[13 + i])
    if camera:
        cam = bd.add(Camera(st=LINK_ST, save_dir=save_dir, save_every=25, link="world",
                            name="camera"))
        for i in range(13):
            bd.connect(plant[i], cam[i])
        sc_cam = bd.add(Scope(n_in=2, labels=["frame_seq", "age [s]"], name="scope_camera"))
        bd.connect(cam[0], sc_cam[0])
        bd.connect(cam[1], sc_cam[1])

    # ---- 기록 ----
    sc_pos = bd.add(Scope(n_in=3, labels=["N [m]", "E [m]", "D [m]"], name="scope_pos"))
    for i in range(3):
        bd.connect(plant[7 + i], sc_pos[i])
    alt = bd.add(Gain(-1.0, name="altitude"))       # 고도 = −D
    bd.connect(plant[9], alt)
    sc_alt = bd.add(Scope(n_in=5, labels=["고도 [m]", "거리계 [m]", "거리 유효", "지면 높이 [m]",
                                          "충돌"], name="scope_alt"))
    bd.connect(alt, sc_alt[0])
    bd.connect(rng[0], sc_alt[1])
    bd.connect(rng[1], sc_alt[2])
    bd.connect(link[2], sc_alt[3])
    bd.connect(link[1], sc_alt[4])
    return bd, sc_pos, sc_alt


def summary(sc_pos, sc_alt, collided=False):
    """최고 고도, 최소 유효 거리, 충돌 여부, 마지막 위치.

    collided: 충돌로 멈췄는가 — 충돌 출력은 한 샘플 늦어 멈춘 순간의 충돌은 Scope 에 없다."""
    if not sc_alt.t:
        return "기록 없음"
    alt, rng, valid, ground, hit = sc_alt.data
    ranges = [r for r, v in zip(rng, valid) if v > 0.5]
    n, e, d = (ch[-1] for ch in sc_pos.data)
    lines = [f"  시간 {sc_alt.t[-1]:.1f} s 까지",
             f"  최고 고도 {max(alt):.1f} m",
             f"  거리계 최소 {min(ranges):.1f} m" if ranges else "  거리계 유효 값 없음",
             f"  지면 높이 범위 {min(ground):.1f} ~ {max(ground):.1f} m",
             f"  충돌 {'있음' if collided or max(hit) > 0.5 else '없음'}",
             f"  마지막 위치 NED = [{n:.1f}, {e:.1f}, {d:.1f}]"]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="SENTIERY 3D 월드에서 쿼드 순회 비행 (loopsym 이 물리)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--waypoints", default=DEFAULT_WAYPOINTS,
                    help='"N,E,D; N,E,D; ..." 출발 패드 기준 NED [m]')
    ap.add_argument("--t-end", type=float, default=180.0)
    ap.add_argument("--no-camera", action="store_true")
    ap.add_argument("--save-dir", default="ex12_frames", help="카메라 영상을 1 초마다 남길 폴더")
    a = ap.parse_args(argv)

    bd, sc_pos, sc_alt = build(a.host, a.port, a.waypoints, camera=not a.no_camera,
                               save_dir=a.save_dir)
    status, collided = 0, False
    try:
        Simulator(bd).run(a.t_end, DT)
        print("비행 완료")
    except WorldLinkError as e:             # 충돌(WorldCollision)·연결 문제
        print(f"중단: {e}")
        status, collided = 1, isinstance(e, WorldCollision)
    print(summary(sc_pos, sc_alt, collided))
    if sc_alt.t:
        here = os.path.dirname(os.path.abspath(__file__))
        out = render_html(bd, os.path.join(here, "ex12_diagram.html"),
                          title="ex12 — SENTIERY 3D 월드 순회 비행", t_end=a.t_end, dt=DT,
                          embed_scopes=True)
        print("뷰어:", out)
    return status


if __name__ == "__main__":
    sys.exit(main())
