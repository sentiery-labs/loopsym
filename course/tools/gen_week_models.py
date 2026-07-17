"""후반부(8~15주차) 모델 JSON 생성기 — 뼈대와 정답의 정본은 이 파일 하나다.

    python course/tools/gen_week_models.py

각 주차의 과제는 '모델 JSON 제출'(curriculum §채점 인프라 4): 학생이 뷰어로
다이어그램을 완성해 weekNN_model.json 으로 저장하면 채점기가 load 후 실행한다.
- weekNN/weekNN_model.json  = 뼈대 (핵심 배선/파라미터가 빠져 있어 채점 FAIL)
- solutions/weekNN_model.json = 정답 (교사용 — 채점 PASS)

뼈대는 "덜 이어진 다이어그램"이다: 블록은 다 놓여 있고, ★로 시작하는 이름의
블록 주변 배선/파라미터가 학생 몫이다 (뷰어에서 열면 무엇이 빠졌는지 보인다).
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COURSE = os.path.dirname(HERE)
ROOT = os.path.dirname(COURSE)
sys.path.insert(0, ROOT)

from loopsym import (                                     # noqa: E402
    Constant, Diagram, IMU, Mixer, QuadPlant, Scope, Step, Subsystem,
    AttitudeController, ComplementaryFilter, PositionController,
    RateController, WaypointManager,
)
from loopsym.viz import export_json                       # noqa: E402

DT = 0.004


# ---------------------------------------------------------------- 공용 조립
def att_rate_chain(bd, plant, att, rate, mix, gyro_src=None):
    """자세+각속도+믹서 공통 배선. gyro_src 지정 시 rate 피드백이 그 블록 경유."""
    for i in range(4):
        bd.connect(plant[i], att[i])
    for i in range(3):
        bd.connect(att[i], rate[i])
        bd.connect((gyro_src or plant)[i if gyro_src else 4 + i], rate[3 + i])
        bd.connect(rate[i], mix[i])
    for i in range(4):
        bd.connect(mix[i], plant[i])


def pos_feedback(bd, plant, pos):
    for i in range(3):
        bd.connect(plant[7 + i], pos[4 + i])   # pos N/E/D
        bd.connect(plant[10 + i], pos[7 + i])  # vel N/E/D


def scope_pos(bd, plant):
    sc = bd.add(Scope(n_in=3, labels=["N", "E", "D"], name="scope_pos"))
    for i in range(3):
        bd.connect(plant[7 + i], sc[i])
    return sc


# ---------------------------------------------------------------- 8주차
# 개루프: 6-DoF + 모터 상수 4개. 과제 = 호버 추력을 손 계산해(mg = N·kF·u)
# ★hover_cmd 에 넣기. 뼈대(0.0)는 자유낙하 → FAIL.
def week08(solved):
    bd = Diagram()
    plant = bd.add(QuadPlant(z0=-5.0, name="quad"))
    cmd = bd.add(Constant(0.5 if solved else 0.0, name="★hover_cmd"))
    for i in range(4):
        bd.connect(cmd, plant[i])
    scope_pos(bd, plant)
    sc = bd.add(Scope(n_in=2, labels=["qw", "p"], name="scope_att"))
    bd.connect(plant[0], sc[0]); bd.connect(plant[4], sc[1])
    return bd


# ---------------------------------------------------------------- 9주차
# rate 폐루프만: rate_sp(yaw 0.5rad/s 회전 명령) 추종. 뼈대는 rate 피드백
# 3줄(★)이 안 이어져 있다 → 컴파일 에러(미연결) → FAIL.
def week09(solved):
    bd = Diagram()
    plant = bd.add(QuadPlant(z0=-5.0, name="quad"))
    rate = bd.add(RateController(st=DT, name="rate_ctrl"))
    mix = bd.add(Mixer(name="mixer"))
    zero = bd.add(Constant(0.0, name="p_sp"))
    zero2 = bd.add(Constant(0.0, name="q_sp"))
    rsp = bd.add(Step(t_on=1.0, height=0.5, name="r_sp"))
    thr = bd.add(Constant(0.5, name="hover_thr"))
    bd.connect(zero, rate[0]); bd.connect(zero2, rate[1]); bd.connect(rsp, rate[2])
    if solved:                                   # ★학생 몫: rate 피드백 배선
        for i in range(3):
            bd.connect(plant[4 + i], rate[3 + i])
    for i in range(3):
        bd.connect(rate[i], mix[i])
    bd.connect(thr, mix[3])
    for i in range(4):
        bd.connect(mix[i], plant[i])
    sc = bd.add(Scope(n_in=2, labels=["r_sp", "r"], name="★scope_rate"))
    bd.connect(rsp, sc[0]); bd.connect(plant[6], sc[1])
    return bd


# ---------------------------------------------------------------- 10주차
# 호버 폐루프 완성 (드론이 처음 뜨는 주): 위치→자세→각속도→믹서→플랜트.
# 뼈대는 캐스케이드 연결(★pos→att, att→rate)이 빠져 있다.
def week10(solved):
    bd = Diagram()
    plant = bd.add(QuadPlant(z0=-5.0, name="quad"))
    pos = bd.add(PositionController(st=DT, name="★pos_ctrl"))
    att = bd.add(AttitudeController(name="★att_ctrl"))
    rate = bd.add(RateController(st=DT, name="rate_ctrl"))
    mix = bd.add(Mixer(name="mixer"))
    n_sp = bd.add(Step(t_on=0.5, height=2.0, name="north_sp"))
    e_sp = bd.add(Constant(0.0, name="east_sp"))
    d_sp = bd.add(Constant(-6.0, name="down_sp"))
    yaw_sp = bd.add(Constant(0.0, name="yaw_sp"))
    for i, src in enumerate((n_sp, e_sp, d_sp, yaw_sp)):
        bd.connect(src, pos[i])
    pos_feedback(bd, plant, pos)
    for i in range(4):
        bd.connect(plant[i], att[i])
    if solved:                                   # ★학생 몫: 캐스케이드 연결
        for i in range(3):
            bd.connect(pos[i], att[4 + i])       # att_cmd
            bd.connect(att[i], rate[i])          # rate_sp
        bd.connect(pos[3], mix[3])               # thrust
    for i in range(3):
        bd.connect(plant[4 + i], rate[3 + i])
        bd.connect(rate[i], mix[i])
    for i in range(4):
        bd.connect(mix[i], plant[i])
    scope_pos(bd, plant)
    return bd


# ---------------------------------------------------------------- 11주차
# 10주차 완성본 + IMU 삽입: rate 피드백이 IMU gyro 를 경유해야 하고,
# fidelity="noisy" + 자이로 바이어스가 있어도 미션이 성립해야 한다.
# 뼈대 = 10주차 정답 (IMU 없음) → 구조 검사 FAIL.
def week11(solved):
    bd = week10(solved=True)
    if not solved:
        return bd
    plant = next(b for b in bd.blocks if b.name == "quad")
    rate = next(b for b in bd.blocks if b.name == "rate_ctrl")
    imu = bd.add(IMU(fidelity="noisy", gyro_bias=0.02, gyro_nd=1e-3,
                     seed=0, st=DT, name="imu"))
    for i in range(4):
        bd.connect(plant[i], imu[i])
    for i in range(3):
        bd.connect(plant[4 + i], imu[4 + i])
        bd.connect(plant[10 + i], imu[7 + i])
    # rate 피드백 재배선: 참값 → IMU gyro
    from loopsym.core import Port
    for i in range(3):
        del bd.wires[Port(rate, 3 + i)]
        bd.connect(imu[i], rate[3 + i])
    return bd


# ---------------------------------------------------------------- 12주차
# 11주차 + ComplementaryFilter: rate 피드백 = CF 의 바이어스 보정 각속도.
# (자세 피드백은 참값 유지 — CF 를 제어 자세에 단독 사용하면 비력 특성으로
#  발산한다: 노트북 이론 참조. 여기서는 '자이로 바이어스 제거'가 목표.)
# 뼈대 = 11주차 정답 (CF 없음) → 구조 검사 FAIL.
def week12(solved):
    bd = week11(solved=True)
    if not solved:
        return bd
    imu = next(b for b in bd.blocks if b.name == "imu")
    rate = next(b for b in bd.blocks if b.name == "rate_ctrl")
    cf = bd.add(ComplementaryFilter(st=DT, name="cf"))
    for i in range(6):
        bd.connect(imu[i], cf[i])
    from loopsym.core import Port
    for i in range(3):
        del bd.wires[Port(rate, 3 + i)]
        bd.connect(cf[4 + i], rate[3 + i])       # omega_est (바이어스 보정)
    return bd


# ---------------------------------------------------------------- 13주차
# 미션: WaypointManager 로 웨이포인트 순회. 뼈대는 wp 블록이 놓여만 있고
# pos_sp 가 아직 상수 → 순회 안 함 → FAIL.
def week13(solved):
    bd = Diagram()
    plant = bd.add(QuadPlant(z0=-5.0, name="quad"))
    pos = bd.add(PositionController(st=DT, name="pos_ctrl"))
    att = bd.add(AttitudeController(name="att_ctrl"))
    rate = bd.add(RateController(st=DT, name="rate_ctrl"))
    mix = bd.add(Mixer(name="mixer"))
    wp = bd.add(WaypointManager(waypoints="2,0,-6; 2,2,-6; 0,0,-5",
                                radius=0.5, st=DT, name="★wp_manager"))
    yaw_sp = bd.add(Constant(0.0, name="yaw_sp"))
    if solved:                                   # ★학생 몫: wp 배선
        for i in range(3):
            bd.connect(plant[7 + i], wp[i])      # 현재 위치 → wp
            bd.connect(wp[i], pos[i])            # pos_sp = wp 출력
    else:                                        # 뼈대: 제자리 유지 상수 (wp 미배선)
        hold = bd.add(Constant(0.0, name="hold_sp"))
        hold_d = bd.add(Constant(-5.0, name="hold_d"))
        bd.connect(hold, pos[0]); bd.connect(hold, pos[1]); bd.connect(hold_d, pos[2])
        # wp 입력도 임시 연결 — 뼈대가 그대로 '실행'은 되게 (제자리 호버).
        # 학생 과제 = 이 임시 배선을 위치 피드백/pos_sp 로 갈아끼우기.
        bd.connect(hold, wp[0]); bd.connect(hold, wp[1]); bd.connect(hold_d, wp[2])
    bd.connect(yaw_sp, pos[3])
    pos_feedback(bd, plant, pos)
    att_rate_chain(bd, plant, att, rate, mix)
    for i in range(3):
        bd.connect(pos[i], att[4 + i])
        # att_rate_chain 이 rate_sp/피드백을 이미 배선
    bd.connect(pos[3], mix[3])
    sc = scope_pos(bd, plant)
    sw = bd.add(Scope(n_in=1, labels=["wp_idx"], name="scope_wp"))
    bd.connect(wp[3], sw[0])
    return bd


# ---------------------------------------------------------------- 14주차
# "같은 다이어그램, 다른 기체": 13주차 미션 모델을 그대로 제출하되, 채점기가
# 기체 질량/관성을 +30% 로 바꿔도(m=1.3) 미션이 완주돼야 한다 (fidelity 사다리
# 의 소프트웨어판 — Gazebo Bridge[P44b] 결정 전 대체). 뼈대 = 13주차 뼈대.
def week14(solved):
    return week13(solved)


# ---------------------------------------------------------------- 15주차
# 종합 프로젝트 자동 채점분(40%): 미션(웨이포인트) + noisy IMU + CF 전부.
# 뼈대 = 13주차 정답에서 IMU/CF 가 빠진 것 (참값 피드백) → 구조 검사 FAIL.
def week15(solved):
    bd = week13(solved=True)
    if not solved:
        return bd
    plant = next(b for b in bd.blocks if b.name == "quad")
    rate = next(b for b in bd.blocks if b.name == "rate_ctrl")
    imu = bd.add(IMU(fidelity="noisy", gyro_bias=0.02, gyro_nd=1e-3,
                     seed=0, st=DT, name="imu"))
    cf = bd.add(ComplementaryFilter(st=DT, name="cf"))
    for i in range(4):
        bd.connect(plant[i], imu[i])
    for i in range(3):
        bd.connect(plant[4 + i], imu[4 + i])
        bd.connect(plant[10 + i], imu[7 + i])
    for i in range(6):
        bd.connect(imu[i], cf[i])
    from loopsym.core import Port
    for i in range(3):
        del bd.wires[Port(rate, 3 + i)]
        bd.connect(cf[4 + i], rate[3 + i])
    return bd


WEEK_BUILDERS = {8: week08, 9: week09, 10: week10, 11: week11,
                 12: week12, 13: week13, 14: week14, 15: week15}


def main():
    for n, build in WEEK_BUILDERS.items():
        wdir = os.path.join(COURSE, f"week{n:02d}")
        os.makedirs(wdir, exist_ok=True)
        for solved, dst in ((False, os.path.join(wdir, f"week{n:02d}_model.json")),
                            (True, os.path.join(COURSE, "solutions", f"week{n:02d}_model.json"))):
            bd = build(solved)
            with open(dst, "w", encoding="utf-8") as f:
                json.dump(export_json(bd), f, ensure_ascii=False, indent=1)
            print("생성:", os.path.relpath(dst, COURSE))


if __name__ == "__main__":
    main()
