"""예제 9 — PX4 v1.16 화이트박스: 제어기 '안에 들어가기'.

ex7 은 검증된 제어기 블록(한 덩어리)을 썼다. 이 예제는 같은 알고리즘을
**기본 블록(Gain/Sum/Saturation/UnitDelay/PyFunction)으로 조립한 서브시스템**
으로 만든다 — 뷰어에서 더블클릭으로 들어가면 PX4 내부 신호가 그대로 보인다.
쿼터니언 좌표변환만 전용 블록(EulerToQuat/QuatAttitudeError/AccelToAttitude,
= Simulink 블록판의 MATLAB Function 블록 상당)이다.

계층 (mc/build_px4_pos_test_blocks.m 의 loopsym 판):
  PX4_PositionControl
    ├─ XY_Control       위치P(0.95) → 속도한계(12) → 속도PI(1.8/0.4) → acc_xy
    ├─ Z_Control        위치P(1.0) → 승강한계(-3/+1.5) → 속도PI(4/2) → acc_z
    └─ AccelToAttitude  acc_sp → att_cmd + thrust  (PX4 실소스)
  PX4_AttitudeControl   EulerToQuat → QuatAttitudeError → att_p Gain → rate 한계
  PX4_RateControl
    └─ Rate_Roll/Pitch/Yaw   PID + anti-windup(ifac) + D항 필터링 미분
                             (yaw 는 D=0 + 토크 LPF 2Hz)
  QuadXMixer, QuadPlant  (할당/플랜트는 검증 블록 그대로)

실행:  python examples/ex9_px4_whitebox.py
  → ex7 모놀리식 제어기와 **동일 궤적**임을 확인(교차 검증) + ex9_diagram.html
"""

import math
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loopsym import (
    Constant, Diagram, Gain, Inport, Outport, PyFunction, Saturation, Scope,
    Simulator, Step, Subsystem, Sum, UnitDelay, render_html,
    QuadPlant, QuadXMixer, EulerToQuat, QuatAttitudeError, AccelToAttitude,
)

DT = 0.004
G0 = 9.80665                     # CONSTANTS_ONE_G (제어기 쪽 표준중력)


# ------------------------------------------------------------------ 공용 조각
def clamped_integrator(d, u_port, gain, lim, name):
    """포화 누적기 x(k+1)=sat(x(k)+gain·u(k)) — MPC/MC 적분항의 블록 구현.

    반환: (적분 출력 포트 = UnitDelay(x(k)))."""
    g = d.add(Gain(k=gain, name=f"{name}_Ki_dt"))
    s = d.add(Sum("++", name=f"{name}_acc"))
    sat = d.add(Saturation(lo=-lim, hi=lim, name=f"{name}_lim"))
    ud = d.add(UnitDelay(st=DT, name=f"{name}_z1"))
    d.connect(u_port, g)
    d.connect(g, s[0]); d.connect(ud, s[1])
    d.connect(s, sat); d.connect(sat, ud)
    return ud


def alpha_filter(d, u_port, cutoff, name):
    """PX4 AlphaFilter: y(k) = y(k-1) + a·(u(k) − y(k-1)),  a = dt/(dt+1/2πfc)."""
    a = DT / (DT + 1.0 / (2.0 * math.pi * cutoff))
    diff = d.add(Sum("+-", name=f"{name}_diff"))
    ga = d.add(Gain(k=a, name=f"{name}_a"))
    add = d.add(Sum("++", name=f"{name}_add"))
    ud = d.add(UnitDelay(st=DT, name=f"{name}_z1"))
    d.connect(u_port, diff[0]); d.connect(ud, diff[1])
    d.connect(diff, ga)
    d.connect(ud, add[0]); d.connect(ga, add[1])
    d.connect(add, ud)
    return add                    # y(k) (필터 갱신값)


# ------------------------------------------------------------ Rate 축 서브시스템
def build_rate_axis(kp, ki, kd, int_lim, yaw_lpf=None):
    """한 축 각속도 PID (rate_control.cpp) — in: rate_sp, rate / out: torque."""
    d = Diagram()
    sp = d.add(Inport(0, name="rate_sp"))
    w = d.add(Inport(1, name="rate"))
    out = d.add(Outport(0, name="torque"))

    err = d.add(Sum("+-", name="err"))
    d.connect(sp, err[0]); d.connect(w, err[1])

    p = d.add(Gain(k=kp, name="P"))
    d.connect(err, p)

    # I: anti-windup ifac = max(0, 1-(e/400°)²) 를 곱한 뒤 포화 누적
    ifac = d.add(PyFunction(
        "f = u0 / (400.0 * pi / 180.0)\ny = max(0.0, 1.0 - f * f) * u0",
        n_in=1, name="ifac"))
    d.connect(err, ifac)
    i_out = clamped_integrator(d, ifac, ki * DT, int_lim, "I")

    tq = d.add(Sum("++-", name="pid_sum"))
    d.connect(p, tq[0]); d.connect(i_out, tq[1])

    # D: 각가속도 = 필터링 미분(30Hz) — (w - z¹w)/dt → AlphaFilter → Kd
    wd = d.add(UnitDelay(st=DT, name="w_z1"))
    raw = d.add(Sum("+-", name="dw"))
    dgain = d.add(Gain(k=1.0 / DT, name="inv_dt"))
    d.connect(w, wd)
    d.connect(w, raw[0]); d.connect(wd, raw[1])
    d.connect(raw, dgain)
    angacc = alpha_filter(d, dgain, 30.0, "angacc")
    kd_g = d.add(Gain(k=kd, name="D"))
    d.connect(angacc, kd_g)
    d.connect(kd_g, tq[2])

    if yaw_lpf:                   # yaw 토크 저역통과 (MC_YAW_TQ_CUTOFF)
        lpf = alpha_filter(d, tq, yaw_lpf, "yaw_tq")
        d.connect(lpf, out)
    else:
        d.connect(tq, out)
    return d


def build_rate_control():
    """PX4_RateControl — in: rate_sp(3), rate(3) / out: torque(3)."""
    d = Diagram()
    ins = [d.add(Inport(i, name=n)) for i, n in enumerate(
        ["p_sp", "q_sp", "r_sp", "p", "q", "r"])]
    outs = [d.add(Outport(i, name=f"t{ax}")) for i, ax in enumerate("xyz")]
    gains = [(0.15, 0.20, 0.003, 0.30, None),        # MC_ROLLRATE_*
             (0.15, 0.20, 0.003, 0.30, None),        # MC_PITCHRATE_*
             (0.20, 0.10, 0.0, 0.30, 2.0)]           # MC_YAWRATE_* + TQ_CUTOFF
    for i, (kp, ki, kd, il, lpf) in enumerate(gains):
        ax = d.add(Subsystem(build_rate_axis(kp, ki, kd, il, lpf),
                             name=f"Rate_{['Roll','Pitch','Yaw'][i]}"))
        d.connect(ins[i], ax[0]); d.connect(ins[3 + i], ax[1])
        d.connect(ax, outs[i])
    return d


# ---------------------------------------------------------- Attitude 서브시스템
def build_attitude_control():
    """PX4_AttitudeControl — in: q(4), att_cmd(3) / out: rate_sp(3)."""
    d = Diagram()
    qin = [d.add(Inport(i, name=f"q{c}")) for i, c in enumerate("wxyz")]
    cmd = [d.add(Inport(4 + i, name=n)) for i, n in enumerate(
        ["roll_cmd", "pitch_cmd", "yaw_cmd"])]
    e2q = d.add(EulerToQuat(name="eul2quat"))
    err = d.add(QuatAttitudeError(name="att_error"))
    for i in range(3):
        d.connect(cmd[i], e2q[i])
    for i in range(4):
        d.connect(qin[i], err[i])
        d.connect(e2q[i], err[4 + i])
    # rate_sp = eq · att_p, 한계 MC_*RATE_MAX  (yaw P 는 2.8/yaw_w)
    att_p = (6.5, 6.5, 2.8 / 0.4)
    lim = (220.0, 220.0, 200.0)
    for i in range(3):
        g = d.add(Gain(k=att_p[i], name=f"att_p_{'rpy'[i]}"))
        s = d.add(Saturation(lo=-lim[i] * math.pi / 180, hi=lim[i] * math.pi / 180,
                             name=f"rate_lim_{'rpy'[i]}"))
        o = d.add(Outport(i, name=f"{'pqr'[i]}_sp"))
        d.connect(err[i], g); d.connect(g, s); d.connect(s, o)
    return d


# ---------------------------------------------------------- Position 서브시스템
def build_xy_control():
    """XY: 위치P → 속도한계(수평 결합) → 속도PI → acc_xy."""
    d = Diagram()
    sp = [d.add(Inport(i, name=f"{c}_sp")) for i, c in enumerate("ne")]
    pos = [d.add(Inport(2 + i, name=f"{c}")) for i, c in enumerate("ne")]
    vel = [d.add(Inport(4 + i, name=f"v{c}")) for i, c in enumerate("ne")]
    # 위치 P (MPC_XY_P) → 수평 속도한계 12 m/s (벡터 크기 클램프라 2축 결합)
    vlim = d.add(PyFunction(
        "s = hypot(u0, u1)\nk = 12.0 / s if s > 12.0 else 1.0\ny0 = u0 * k\ny1 = u1 * k",
        n_in=2, n_out=2, name="vel_limit"))
    for i in range(2):
        pe = d.add(Sum("+-", name=f"pos_err_{'ne'[i]}"))
        pp = d.add(Gain(k=0.95, name=f"XY_P_{'ne'[i]}"))
        d.connect(sp[i], pe[0]); d.connect(pos[i], pe[1])
        d.connect(pe, pp); d.connect(pp, vlim[i])
    for i in range(2):
        ve = d.add(Sum("+-", name=f"vel_err_{'ne'[i]}"))
        vp = d.add(Gain(k=1.8, name=f"VEL_P_{'ne'[i]}"))
        acc = d.add(Sum("++", name=f"acc_{'ne'[i]}"))
        o = d.add(Outport(i, name=f"acc_{'ne'[i]}"))
        d.connect(vlim[i], ve[0]); d.connect(vel[i], ve[1])
        d.connect(ve, vp)
        i_out = clamped_integrator(d, ve, 0.4 * DT, 4.0, f"I_{'ne'[i]}")
        d.connect(vp, acc[0]); d.connect(i_out, acc[1])
        d.connect(acc, o)
    return d


def build_z_control():
    """Z: 위치P → 승강속도한계 → 속도PI → acc_z (px4_alt_control 캐스케이드)."""
    d = Diagram()
    sp = d.add(Inport(0, name="d_sp"))
    pos = d.add(Inport(1, name="d"))
    vel = d.add(Inport(2, name="vd"))
    o = d.add(Outport(0, name="acc_d"))
    pe = d.add(Sum("+-", name="pos_err"))
    pp = d.add(Gain(k=1.0, name="Z_P"))
    vsat = d.add(Saturation(lo=-3.0, hi=1.5, name="vz_lim"))   # UP 3.0 / DN 1.5
    d.connect(sp, pe[0]); d.connect(pos, pe[1])
    d.connect(pe, pp); d.connect(pp, vsat)
    ve = d.add(Sum("+-", name="vel_err"))
    vp = d.add(Gain(k=4.0, name="VZ_P"))
    acc = d.add(Sum("++", name="acc"))
    d.connect(vsat, ve[0]); d.connect(vel, ve[1])
    d.connect(ve, vp)
    i_out = clamped_integrator(d, ve, 2.0 * DT, 4.0, "I")
    d.connect(vp, acc[0]); d.connect(i_out, acc[1])
    d.connect(acc, o)
    return d


def build_position_control():
    """PX4_PositionControl — in: pos_sp(3)+yaw_sp+pos(3)+vel(3) / out: att_cmd(3)+thrust."""
    d = Diagram()
    ins = [d.add(Inport(i, name=n)) for i, n in enumerate(
        ["n_sp", "e_sp", "d_sp", "yaw_sp", "n", "e", "dpos", "vn", "ve", "vd"])]
    xy = d.add(Subsystem(build_xy_control(), name="XY_Control"))
    z = d.add(Subsystem(build_z_control(), name="Z_Control"))
    a2a = d.add(AccelToAttitude(name="accel_to_att"))
    for i, src in enumerate([ins[0], ins[1], ins[4], ins[5], ins[7], ins[8]]):
        d.connect(src, xy[i])
    for i, src in enumerate([ins[2], ins[6], ins[9]]):
        d.connect(src, z[i])
    d.connect(xy[0], a2a[0]); d.connect(xy[1], a2a[1]); d.connect(z, a2a[2])
    d.connect(ins[3], a2a[3])
    for i, n in enumerate(["roll_cmd", "pitch_cmd", "yaw_cmd", "thrust"]):
        o = d.add(Outport(i, name=n))
        d.connect(a2a[i], o)
    return d


# ------------------------------------------------------------------ 최상위 조립
def build(scenario="pos"):
    """ex7 과 같은 시나리오의 화이트박스 판."""
    bd = Diagram()
    plant = bd.add(QuadPlant(z0=-5.0, name="quad"))
    pos = bd.add(Subsystem(build_position_control(), name="PX4_PositionControl"))
    att = bd.add(Subsystem(build_attitude_control(), name="PX4_AttitudeControl"))
    rate = bd.add(Subsystem(build_rate_control(), name="PX4_RateControl"))
    mix = bd.add(QuadXMixer(name="mixer"))

    n_sp = bd.add(Step(t_on=0.5, height=2.0, name="north_sp"))
    e_sp = bd.add(Constant(0.0, name="east_sp"))
    d_sp = bd.add(Constant(-6.0, name="down_sp"))
    yaw_sp = bd.add(Constant(0.0, name="yaw_sp"))
    for i, src in enumerate((n_sp, e_sp, d_sp, yaw_sp)):
        bd.connect(src, pos[i])
    for i in range(3):
        bd.connect(plant[7 + i], pos[4 + i])
        bd.connect(plant[10 + i], pos[7 + i])
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

    sc = bd.add(Scope(n_in=3, labels=["N [m]", "E [m]", "D [m]"], name="scope_pos"))
    for i in range(3):
        bd.connect(plant[7 + i], sc[i])
    return bd, sc


if __name__ == "__main__":
    # 화이트박스 실행
    bd, sc = build()
    Simulator(bd).run(8.0, DT)
    n, e, d = (ch[-1] for ch in sc.data)
    print(f"화이트박스 최종 NED = [{n:.3f}, {e:.3f}, {d:.3f}]  (목표 [2, 0, -6])")

    # 교차 검증: ex7 모놀리식 판과 궤적 비교 (블록판 ↔ 함수판 동등성)
    from ex7_drone_hover import build as build_mono
    bd2, sc2 = build_mono()
    Simulator(bd2).run(8.0, DT)
    dmax = max(abs(a - b) for cha, chb in zip(sc.data, sc2.data)
               for a, b in zip(cha, chb))
    print(f"모놀리식(ex7) 대비 최대 궤적 차이 = {dmax:.2e} m")
    assert dmax < 1e-6, "화이트박스 ↔ 모놀리식 불일치"

    here = os.path.dirname(os.path.abspath(__file__))
    out = render_html(bd, os.path.join(here, "ex9_diagram.html"),
                      title="ex9 — PX4 v1.16 화이트박스 (더블클릭으로 진입)")
    print("뷰어:", out, " (서브시스템 더블클릭 → PX4 내부로)")
