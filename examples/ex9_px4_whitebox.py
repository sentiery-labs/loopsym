"""예제 9 — PX4 v1.16 화이트박스: 제어기 '안에 들어가기'.

ex7 은 검증된 제어기 블록(한 덩어리)을 썼다. 이 예제는 같은 알고리즘을
**기본 블록(Gain/Sum/Saturation/UnitDelay/PyFunction)으로 조립한 서브시스템**
으로 만든다 — 뷰어에서 더블클릭으로 들어가면 PX4 내부 신호가 그대로 보인다.
Position/Rate 서브시스템은 입력마다 ZeroOrderHold(st=DT)를 달아 FC 처럼
샘플 시점의 값으로만 계산한다 (한 덩어리 제어기 블록의 샘플 규칙과 동일).
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
  Mixer(quad_x)
  QuadPlant_6DoF        ← 플랜트도 화이트박스: 모터→힘/모멘트→강체 흐름
    ├─ Motor_Dynamics   모터 명령 [0..1] → 포화 → kF → 로터 추력 [N]
    ├─ Forces_Moments   로터 추력 → 동체 토크(3) + 총추력  (quad-X 기하)
    └─ Body_Dynamics    6-DoF 강체: 13-상태 미분(쿼터니언/오일러 방정식)
                        + 적분기 13개 (RK4 가 적분)

실행:  python examples/ex9_px4_whitebox.py
  → ex7 모놀리식 제어기와 **동일 궤적**임을 확인(교차 검증) + ex9_diagram.html
"""

import math
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loopsym import (
    Constant, Diagram, Gain, Inport, Integrator, Outport, PyFunction, Saturation,
    Scope, Simulator, Step, Subsystem, Sum, UnitDelay, ZeroOrderHold, render_html,
    Mixer, QuadPlant, EulerToQuat, QuatAttitudeError, AccelToAttitude,
)

DT = 0.004
G0 = 9.80665                     # CONSTANTS_ONE_G (제어기 쪽 표준중력)


# ------------------------------------------------------------------ 공용 조각
def sampled_inputs(d, names):
    """FC 가 센서·명령을 읽는 순간: Inport 마다 ZOH(st=DT) 를 달아 반환.

    이 뒤의 기본 블록(Gain/Sum…)은 샘플 사이에 붙잡힌 값만 본다 — 한 덩어리
    제어기 블록(ex7)이 샘플 시점에만 계산되는 것과 같은 디지털 제어기."""
    out = []
    for i, n in enumerate(names):
        p = d.add(Inport(i, name=n))
        z = d.add(ZeroOrderHold(st=DT, name=f"{n}_zoh"))
        d.connect(p, z)
        out.append(z)
    return out


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
    ins = sampled_inputs(d, ["p_sp", "q_sp", "r_sp", "p", "q", "r"])
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
    ins = sampled_inputs(
        d, ["n_sp", "e_sp", "d_sp", "yaw_sp", "n", "e", "dpos", "vn", "ve", "vd"])
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


# ------------------------------------------------------------ Plant 화이트박스
# 검증본 QuadPlant(quad_x 기본값: m=1, I=(.02,.02,.04), arm=.25, cM=.06)와
# 같은 방정식을 블록 흐름으로 편 것 — 모터 → 힘/모멘트 → 강체 6-DoF.
def build_motor_dynamics(k_f):
    """모터 명령 [0..1] → 포화 → 추력상수 kF → 로터 추력 [N]."""
    d = Diagram()
    for i in range(4):
        cmd = d.add(Inport(i, name=f"cmd{i + 1}"))
        sat = d.add(Saturation(lo=0.0, hi=1.0, name=f"sat{i + 1}"))
        kf = d.add(Gain(k=k_f, name=f"kF{i + 1}"))
        o = d.add(Outport(i, name=f"f{i + 1}"))
        d.connect(cmd, sat); d.connect(sat, kf); d.connect(kf, o)
    return d


def build_body_dynamics(z0):
    """토크(3)+총추력 → 13-상태 6-DoF 미분(PyFunction) → 적분기 13개."""
    d = Diagram()
    ins = [d.add(Inport(i, name=n)) for i, n in enumerate(["tau_x", "tau_y", "tau_z", "T"])]
    # 미분: u0..u12 = 상태(qw qx qy qz | p q r | pN pE pD | vN vE vD), u13..u16 = 입력
    dyn = d.add(PyFunction("\n".join([
        "# 6-DoF 강체 (m=1, Ixx=Iyy=0.02, Izz=0.04, g=9.81)",
        "qw = u0; qx = u1; qy = u2; qz = u3",
        "p = u4; q = u5; r = u6",
        "# 쿼터니언 운동학 + 정규화 보정 (Baumgarte)",
        "c = 0.5 * (1.0 - (qw*qw + qx*qx + qy*qy + qz*qz))",
        "y0 = 0.5*(-qx*p - qy*q - qz*r) + c*qw",
        "y1 = 0.5*( qw*p + qy*r - qz*q) + c*qx",
        "y2 = 0.5*( qw*q - qx*r + qz*p) + c*qy",
        "y3 = 0.5*( qw*r + qx*q - qy*p) + c*qz",
        "# 오일러 방정식 (대각 관성)",
        "y4 = (u13 - (q*0.04*r - r*0.02*q)) / 0.02",
        "y5 = (u14 - (r*0.02*p - p*0.04*r)) / 0.02",
        "y6 = (u15 - (p*0.02*q - q*0.02*p)) / 0.04",
        "# 위치 미분 = 속도",
        "y7 = u10; y8 = u11; y9 = u12",
        "# 병진: 중력 + 추력(동체 -z 를 NED 로 회전)",
        "az = -u16 / 1.0",
        "y10 = 2*(qx*qz + qw*qy) * az",
        "y11 = 2*(qy*qz - qw*qx) * az",
        "y12 = 9.81 + (qw*qw - qx*qx - qy*qy + qz*qz) * az",
    ]), n_in=17, n_out=13, name="deriv_6dof"))
    x0 = [1.0] + [0.0] * 8 + [z0] + [0.0] * 3          # qw=1, pD=z0
    names = ["qw", "qx", "qy", "qz", "p", "q", "r",
             "pN", "pE", "pD", "vN", "vE", "vD"]
    for i in range(13):
        it = d.add(Integrator(x0=x0[i], name=f"int_{names[i]}"))
        o = d.add(Outport(i, name=names[i]))
        d.connect(dyn[i], it); d.connect(it, o)
        d.connect(it, dyn[i])                           # 상태 피드백
    for i in range(4):
        d.connect(ins[i], dyn[13 + i])
    return d


def build_plant_whitebox(z0=0.0):
    """QuadPlant(quad_x) 화이트박스 — in: 모터 4 / out: 상태 13."""
    d = Diagram()
    ins = [d.add(Inport(i, name=f"m{i + 1}")) for i in range(4)]
    motors = d.add(Subsystem(build_motor_dynamics(k_f=1.0 * 9.81 / 2.0),
                             name="Motor_Dynamics"))
    # quad-X 기하: Mx=-arm·Σpy·f, My=arm·Σpx·f, Mz=cM·Σspin·f
    fm = d.add(PyFunction("\n".join([
        "# quad-X: px=(1,-1,1,-1) py=(1,-1,-1,1) spin=(1,1,-1,-1), arm=0.25, cM=0.06",
        "y0 = -0.25 * (u0 - u1 - u2 + u3)",
        "y1 =  0.25 * (u0 - u1 + u2 - u3)",
        "y2 =  0.06 * (u0 + u1 - u2 - u3)",
        "y3 = u0 + u1 + u2 + u3",
    ]), n_in=4, n_out=4, name="Forces_Moments"))
    body = d.add(Subsystem(build_body_dynamics(z0), name="Body_Dynamics"))
    for i in range(4):
        d.connect(ins[i], motors[i])
        d.connect(motors[i], fm[i])
        d.connect(fm[i], body[i])
    for i in range(13):
        o = d.add(Outport(i, name=f"x{i}"))
        d.connect(body[i], o)
    return d


# ------------------------------------------------------------------ 최상위 조립
def build(scenario="pos"):
    """ex7 과 같은 시나리오의 화이트박스 판."""
    bd = Diagram()
    pos = bd.add(Subsystem(build_position_control(), name="PX4_PositionControl"))
    att = bd.add(Subsystem(build_attitude_control(), name="PX4_AttitudeControl"))
    rate = bd.add(Subsystem(build_rate_control(), name="PX4_RateControl"))
    mix = bd.add(Mixer(frame="quad_x", name="mixer"))
    plant = bd.add(Subsystem(build_plant_whitebox(z0=-5.0), name="QuadPlant_6DoF"))

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
                      title="ex9 — PX4 v1.16 화이트박스 (더블클릭으로 진입)",
                      t_end=8.0, dt=DT)
    print("뷰어:", out, " (서브시스템 더블클릭 → PX4 내부로)")
